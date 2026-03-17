from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List

try:
    from chromadb import PersistentClient
except Exception:  # pragma: no cover - dependency guard
    PersistentClient = None

from resume_platform.infrastructure.llm_config import get_embedding_model
from resume_platform.infrastructure.filesystem import init_filesystems, is_initialized
from resume_platform.resume.repository import load_complete_resume_as_dict
from resume_platform.resume.repository import find_resume_versions
from resume_platform.infrastructure.settings import get_settings


COLLECTION_NAME = "resume_entries"


@dataclass
class ChunkRecord:
    id: str
    text: str
    metadata: Dict[str, Any]


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _normalize_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _chunk_id(source: str) -> str:
    digest = hashlib.sha256(source.encode("utf-8")).hexdigest()
    return f"chunk_{digest}"


def _entry_text(entry: Dict[str, Any]) -> str:
    title = _normalize_text(entry.get("title"))
    organization = _normalize_text(entry.get("organization"))
    period = _normalize_text(entry.get("period"))
    location = _normalize_text(entry.get("location"))
    bullets = [
        _normalize_text(bullet)
        for bullet in (entry.get("bullets") or [])
        if _normalize_text(bullet)
    ]

    lines = [
        f"Title: {title}",
        f"Organization: {organization}",
        f"Period: {period}",
        f"Location: {location}",
    ]
    if bullets:
        lines.append("Bullets:")
        lines.extend(f"- {bullet}" for bullet in bullets)
    return "\n".join(lines).strip()


def _entry_signature(entry_type: str, entry: Dict[str, Any]) -> str:
    title = _normalize_text(entry.get("title"))
    organization = _normalize_text(entry.get("organization"))
    period = _normalize_text(entry.get("period"))
    location = _normalize_text(entry.get("location"))
    bullets = [
        _normalize_text(bullet)
        for bullet in (entry.get("bullets") or [])
        if _normalize_text(bullet)
    ]
    payload = {
        "entry_type": entry_type,
        "title": title,
        "organization": organization,
        "period": period,
        "location": location,
        "bullets": bullets,
    }
    return hashlib.sha256(
        json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()


def _build_chunks_from_resume(
    version: str, resume_data: Dict[str, Any]
) -> List[ChunkRecord]:
    chunks: List[ChunkRecord] = []
    sections = resume_data.get("sections") or []

    for section in sections:
        section_type = _normalize_text(section.get("type")).lower()
        if section_type not in {"experience", "projects"}:
            continue

        section_id = _normalize_text(section.get("id"))
        entries = section.get("entries") or []

        for entry_index, entry in enumerate(entries):
            if not isinstance(entry, dict):
                continue

            entry_sig = _entry_signature(section_type, entry)
            entry_text = _entry_text(entry)
            if entry_text:
                entry_metadata: Dict[str, Any] = {
                    "entry_type": section_type,
                    "chunk_level": "entry",
                    "title": _normalize_text(entry.get("title")),
                    "organization": _normalize_text(entry.get("organization")),
                    "period": _normalize_text(entry.get("period")),
                    "location": _normalize_text(entry.get("location")),
                    "section_id": section_id,
                    "entry_index": entry_index,
                    "bullet_index": -1,
                    "versions": version,
                    "entry_sig": entry_sig,
                }
                chunks.append(
                    ChunkRecord(
                        id=_chunk_id(f"entry::{entry_sig}"),
                        text=entry_text,
                        metadata=entry_metadata,
                    )
                )

            bullets = entry.get("bullets") or []
            for bullet_index, bullet in enumerate(bullets):
                bullet_text = _normalize_text(bullet)
                if not bullet_text:
                    continue
                bullet_sig_raw = f"bullet::{entry_sig}::{bullet_text}"
                bullet_id = _chunk_id(bullet_sig_raw)
                bullet_metadata: Dict[str, Any] = {
                    "entry_type": section_type,
                    "chunk_level": "bullet",
                    "title": _normalize_text(entry.get("title")),
                    "organization": _normalize_text(entry.get("organization")),
                    "period": _normalize_text(entry.get("period")),
                    "location": _normalize_text(entry.get("location")),
                    "section_id": section_id,
                    "entry_index": entry_index,
                    "bullet_index": bullet_index,
                    "versions": version,
                    "entry_sig": entry_sig,
                }
                chunks.append(
                    ChunkRecord(
                        id=bullet_id,
                        text=bullet_text,
                        metadata=bullet_metadata,
                    )
                )

    return chunks


def _merge_chunks(chunks: List[ChunkRecord]) -> List[ChunkRecord]:
    merged: Dict[str, ChunkRecord] = {}
    version_sets: Dict[str, set[str]] = {}

    for chunk in chunks:
        if chunk.id not in merged:
            merged[chunk.id] = chunk
            versions = {
                v.strip()
                for v in chunk.metadata.get("versions", "").split(",")
                if v.strip()
            }
            version_sets[chunk.id] = versions
            continue

        existing = merged[chunk.id]
        if existing.text != chunk.text:
            continue

        current_versions = version_sets[chunk.id]
        new_versions = {
            v.strip()
            for v in chunk.metadata.get("versions", "").split(",")
            if v.strip()
        }
        current_versions.update(new_versions)

    for chunk_id, chunk in merged.items():
        versions = sorted(version_sets.get(chunk_id, set()))
        chunk.metadata["versions"] = ",".join(versions)

    return list(merged.values())


def _get_client_and_collection():
    if PersistentClient is None:
        raise RuntimeError(
            "chromadb is not installed. Please install dependencies and run again."
        )
    settings = get_settings()
    client = PersistentClient(path=str(settings.vector_db_dir))
    collection = client.get_or_create_collection(
        name=COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},
    )
    return client, collection


def _ensure_filesystems_initialized() -> None:
    if is_initialized():
        return

    settings = get_settings()
    init_filesystems(settings.resume_fs_url, settings.jd_fs_url)


def _read_status() -> Dict[str, Any]:
    status_path = get_settings().index_status_path
    if not status_path.exists():
        return {
            "stale": True,
            "exists": False,
            "last_built_at": None,
            "last_reason": "index_not_initialized",
        }

    try:
        payload = json.loads(status_path.read_text(encoding="utf-8"))
        if isinstance(payload, dict):
            return payload
    except Exception:
        pass

    return {
        "stale": True,
        "exists": False,
        "last_built_at": None,
        "last_reason": "invalid_status_file",
    }


def _write_status(payload: Dict[str, Any]) -> None:
    status_path = get_settings().index_status_path
    status_path.parent.mkdir(parents=True, exist_ok=True)
    status_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def mark_index_stale(reason: str = "resume_updated") -> Dict[str, Any]:
    status = _read_status()
    status.update(
        {
            "stale": True,
            "last_reason": reason,
            "updated_at": _utc_now_iso(),
        }
    )
    _write_status(status)
    return status


def _batch(items: List[str], batch_size: int = 64) -> List[List[str]]:
    return [
        items[index : index + batch_size] for index in range(0, len(items), batch_size)
    ]


def _as_list(value: Any) -> List[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    try:
        return list(value)
    except TypeError:
        return []


def _split_versions(value: Any) -> List[str]:
    text = _normalize_text(value)
    if not text:
        return []
    return [part.strip() for part in text.split(",") if part.strip()]


def _build_search_result_item(
    *, rank: int, document: str, metadata: Dict[str, Any], distance: Any
) -> Dict[str, Any]:
    similarity = None
    if isinstance(distance, (float, int)):
        similarity = max(0.0, 1.0 - float(distance))

    versions = _split_versions(metadata.get("versions"))
    source = {
        "entry_type": metadata.get("entry_type", ""),
        "chunk_level": metadata.get("chunk_level", ""),
        "title": metadata.get("title", ""),
        "organization": metadata.get("organization", ""),
        "period": metadata.get("period", ""),
        "location": metadata.get("location", ""),
        "section_id": metadata.get("section_id", ""),
        "versions": versions,
    }

    return {
        "rank": rank,
        "score": similarity,
        "score_percent": round(similarity * 100, 2) if similarity is not None else None,
        "text": document,
        "preview": document[:240],
        "source": source,
        "indices": {
            "entry_index": metadata.get("entry_index"),
            "bullet_index": metadata.get("bullet_index"),
        },
        "metadata": metadata,
    }


def _embedding_context(provider: str, embedding_model: Any) -> str:
    model_name = _normalize_text(getattr(embedding_model, "model", "")) or "unknown"
    return f"provider={provider}, model={model_name}"


def _embed_documents_with_validation(
    embedding_model: Any, documents: List[str], provider: str
) -> List[List[float]]:
    try:
        vectors = embedding_model.embed_documents(documents)
    except Exception as exc:
        raise RuntimeError(
            "Failed to generate document embeddings. "
            f"Check embedding endpoint/model compatibility ({_embedding_context(provider, embedding_model)}): {exc}"
        ) from exc

    if vectors is None:
        raise RuntimeError(
            "Embedding API returned no document vectors (None). "
            f"Check embedding endpoint/model compatibility ({_embedding_context(provider, embedding_model)})."
        )
    if not isinstance(vectors, list):
        raise RuntimeError(
            "Embedding API returned an invalid document vectors payload. "
            f"Expected list, got {type(vectors).__name__} ({_embedding_context(provider, embedding_model)})."
        )
    if len(vectors) != len(documents):
        raise RuntimeError(
            "Embedding API returned a mismatched document vector count. "
            f"Expected {len(documents)}, got {len(vectors)} ({_embedding_context(provider, embedding_model)})."
        )
    return vectors


def _embed_query_with_validation(
    embedding_model: Any, query_text: str, provider: str
) -> List[float]:
    try:
        vector = embedding_model.embed_query(query_text)
    except Exception as exc:
        raise RuntimeError(
            "Failed to generate query embedding. "
            f"Check embedding endpoint/model compatibility ({_embedding_context(provider, embedding_model)}): {exc}"
        ) from exc

    if vector is None:
        raise RuntimeError(
            "Embedding API returned no query embedding (None). "
            f"Check embedding endpoint/model compatibility ({_embedding_context(provider, embedding_model)})."
        )
    if not isinstance(vector, list):
        raise RuntimeError(
            "Embedding API returned an invalid query embedding payload. "
            f"Expected list, got {type(vector).__name__} ({_embedding_context(provider, embedding_model)})."
        )
    return vector


def build_index(force_rebuild: bool = False) -> Dict[str, Any]:
    _ensure_filesystems_initialized()
    _, collection = _get_client_and_collection()

    all_chunks: List[ChunkRecord] = []
    versions = find_resume_versions()
    for version in versions:
        resume_data = load_complete_resume_as_dict(version)
        all_chunks.extend(_build_chunks_from_resume(version, resume_data))

    merged_chunks = _merge_chunks(all_chunks)

    existing = collection.get(include=["metadatas", "documents", "embeddings"])
    existing_ids = _as_list(existing.get("ids"))
    existing_documents = _as_list(existing.get("documents"))
    existing_embeddings = _as_list(existing.get("embeddings"))

    existing_by_id: Dict[str, Dict[str, Any]] = {}
    for idx, item_id in enumerate(existing_ids):
        existing_by_id[item_id] = {
            "document": (
                existing_documents[idx] if idx < len(existing_documents) else ""
            ),
            "embedding": (
                existing_embeddings[idx] if idx < len(existing_embeddings) else None
            ),
        }

    target_ids = [chunk.id for chunk in merged_chunks]
    target_set = set(target_ids)

    to_embed_ids: List[str] = []
    to_embed_docs: List[str] = []
    to_embed_meta: List[Dict[str, Any]] = []

    cached_ids: List[str] = []
    cached_docs: List[str] = []
    cached_meta: List[Dict[str, Any]] = []
    cached_embeddings: List[List[float]] = []

    for chunk in merged_chunks:
        existing_item = existing_by_id.get(chunk.id)
        if (
            not force_rebuild
            and existing_item is not None
            and existing_item.get("embedding") is not None
            and existing_item.get("document") == chunk.text
        ):
            cached_ids.append(chunk.id)
            cached_docs.append(chunk.text)
            cached_meta.append(chunk.metadata)
            cached_embeddings.append(existing_item["embedding"])
            continue

        to_embed_ids.append(chunk.id)
        to_embed_docs.append(chunk.text)
        to_embed_meta.append(chunk.metadata)

    if cached_ids:
        collection.upsert(
            ids=cached_ids,
            documents=cached_docs,
            metadatas=cached_meta,
            embeddings=cached_embeddings,
        )

    new_embedding_count = 0
    if to_embed_ids:
        provider = get_settings().embedding_provider
        embedding_model = get_embedding_model(provider)
        embedded_vectors: List[List[float]] = []
        for doc_batch in _batch(to_embed_docs, batch_size=64):
            batch_vectors = _embed_documents_with_validation(
                embedding_model, doc_batch, provider
            )
            embedded_vectors.extend(batch_vectors)

        collection.upsert(
            ids=to_embed_ids,
            documents=to_embed_docs,
            metadatas=to_embed_meta,
            embeddings=embedded_vectors,
        )
        new_embedding_count = len(to_embed_ids)

    stale_ids = [item_id for item_id in existing_ids if item_id not in target_set]
    if stale_ids:
        collection.delete(ids=stale_ids)

    entry_count = sum(
        1 for chunk in merged_chunks if chunk.metadata.get("chunk_level") == "entry"
    )
    bullet_count = sum(
        1 for chunk in merged_chunks if chunk.metadata.get("chunk_level") == "bullet"
    )

    status_payload = {
        "stale": False,
        "exists": True,
        "last_built_at": _utc_now_iso(),
        "last_reason": "manual_rebuild" if force_rebuild else "auto_or_manual_rebuild",
        "versions_indexed": versions,
        "total_chunks": len(merged_chunks),
        "entry_chunks": entry_count,
        "bullet_chunks": bullet_count,
        "cached_embeddings": len(cached_ids),
        "new_embeddings": new_embedding_count,
    }
    _write_status(status_payload)
    return status_payload


def ensure_index_ready() -> Dict[str, Any]:
    status = _read_status()
    if status.get("stale", True) or not status.get("exists", False):
        rebuild_result = build_index(force_rebuild=False)
        rebuild_result["auto_rebuilt"] = True
        return rebuild_result

    status["auto_rebuilt"] = False
    return status


def get_index_status() -> Dict[str, Any]:
    status = _read_status()
    try:
        _, collection = _get_client_and_collection()
        status["collection_count"] = collection.count()
    except Exception:
        status["collection_count"] = 0
    return status


def search_entries(
    query: str,
    entry_type: str | None = None,
    chunk_level: str = "entry",
    top_k: int = 5,
) -> Dict[str, Any]:
    query_text = _normalize_text(query)
    if not query_text:
        return {"error": "Query must not be empty."}

    normalized_level = _normalize_text(chunk_level).lower() or "entry"
    if normalized_level not in {"entry", "bullet"}:
        return {"error": "chunk_level must be one of: entry, bullet."}

    normalized_type = _normalize_text(entry_type).lower()
    if normalized_type in {"all", "both", ""}:
        normalized_type = ""
    if normalized_type and normalized_type not in {"experience", "projects"}:
        return {"error": "entry_type must be one of: experience, projects, all."}

    ensure_state = ensure_index_ready()

    _, collection = _get_client_and_collection()
    provider = get_settings().embedding_provider
    embedding_model = get_embedding_model(provider)
    query_vector = _embed_query_with_validation(embedding_model, query_text, provider)

    where_filter: Dict[str, Any] = {"chunk_level": normalized_level}
    if normalized_type:
        where_filter = {
            "$and": [
                {"chunk_level": normalized_level},
                {"entry_type": normalized_type},
            ]
        }

    result = collection.query(
        query_embeddings=[query_vector],
        n_results=max(1, top_k),
        where=where_filter,
        include=["documents", "metadatas", "distances"],
    )

    documents = (result.get("documents") or [[]])[0]
    metadatas = (result.get("metadatas") or [[]])[0]
    distances = (result.get("distances") or [[]])[0]

    results: List[Dict[str, Any]] = []
    for idx, document in enumerate(documents):
        metadata = metadatas[idx] if idx < len(metadatas) else {}
        distance = distances[idx] if idx < len(distances) else None
        results.append(
            _build_search_result_item(
                rank=idx + 1,
                document=document,
                metadata=metadata,
                distance=distance,
            )
        )

    return {
        "request": {
            "query": query_text,
            "entry_type": normalized_type or "all",
            "chunk_level": normalized_level,
            "top_k": top_k,
        },
        "index_status": ensure_state,
        "result_count": len(results),
        "results": results,
        "matches": results,
    }
