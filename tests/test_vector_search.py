from __future__ import annotations

import sys
from pathlib import Path

from resume_platform import vector_search
from resume_platform.infrastructure import llm_config


def _sample_resume() -> dict:
    return {
        "sections": [
            {
                "id": "experience",
                "type": "experience",
                "entries": [
                    {
                        "title": "ML Engineer",
                        "organization": "OpenAI",
                        "period": "2024-2025",
                        "location": "Remote",
                        "bullets": [
                            "Built distributed systems for inference.",
                            "Improved retrieval quality for resume search.",
                        ],
                    }
                ],
            },
            {
                "id": "projects",
                "type": "projects",
                "entries": [
                    {
                        "title": "Resume MCP",
                        "organization": "Personal",
                        "period": "2025",
                        "location": "Seattle",
                        "bullets": [
                            "Implemented vector search with bullet-level indexing."
                        ],
                    }
                ],
            },
            {"id": "skills", "type": "skills", "content": []},
        ]
    }


class FakeEmbeddings:
    def __init__(self) -> None:
        self.embed_documents_calls: list[list[str]] = []
        self.embed_query_calls: list[str] = []

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        self.embed_documents_calls.append(list(texts))
        return [[float(len(text)), float(index)] for index, text in enumerate(texts)]

    def embed_query(self, text: str) -> list[float]:
        self.embed_query_calls.append(text)
        return [float(len(text)), 1.0]


class FakeCollection:
    def __init__(self, existing: dict[str, dict] | None = None) -> None:
        self.store = existing or {}
        self.last_query: dict | None = None

    def get(self, include: list[str] | None = None) -> dict:
        ids = list(self.store.keys())
        return {
            "ids": ids,
            "documents": [self.store[item_id]["document"] for item_id in ids],
            "embeddings": [self.store[item_id]["embedding"] for item_id in ids],
            "metadatas": [self.store[item_id]["metadata"] for item_id in ids],
        }

    def upsert(
        self,
        *,
        ids: list[str],
        documents: list[str],
        metadatas: list[dict],
        embeddings: list[list[float]],
    ) -> None:
        for item_id, document, metadata, embedding in zip(
            ids, documents, metadatas, embeddings
        ):
            self.store[item_id] = {
                "document": document,
                "metadata": metadata,
                "embedding": embedding,
            }

    def delete(self, ids: list[str]) -> None:
        for item_id in ids:
            self.store.pop(item_id, None)

    def count(self) -> int:
        return len(self.store)

    def query(
        self,
        *,
        query_embeddings: list[list[float]],
        n_results: int,
        where: dict,
        include: list[str],
    ) -> dict:
        self.last_query = {
            "query_embeddings": query_embeddings,
            "n_results": n_results,
            "where": where,
            "include": include,
        }
        return {
            "documents": [
                [
                    "Built distributed systems for inference.",
                    "Implemented vector search with bullet-level indexing.",
                ]
            ],
            "metadatas": [
                [
                    {"entry_type": "experience", "chunk_level": "bullet"},
                    {"entry_type": "projects", "chunk_level": "bullet"},
                ]
            ],
            "distances": [[0.1, 0.4]],
        }


def test_build_chunks_from_resume_extracts_entry_and_bullet_metadata() -> None:
    chunks = vector_search._build_chunks_from_resume("resume_a", _sample_resume())

    assert len(chunks) == 5

    entry_chunk = next(
        chunk for chunk in chunks if chunk.metadata["chunk_level"] == "entry"
    )
    assert entry_chunk.metadata["entry_type"] == "experience"
    assert entry_chunk.metadata["versions"] == "resume_a"
    assert "Title: ML Engineer" in entry_chunk.text
    assert "Bullets:" in entry_chunk.text

    bullet_chunk = next(
        chunk
        for chunk in chunks
        if chunk.metadata["chunk_level"] == "bullet"
        and chunk.metadata["entry_type"] == "projects"
    )
    assert bullet_chunk.text == "Implemented vector search with bullet-level indexing."
    assert bullet_chunk.metadata["title"] == "Resume MCP"
    assert bullet_chunk.metadata["organization"] == "Personal"


def test_merge_chunks_deduplicates_versions() -> None:
    resume = _sample_resume()
    chunks = vector_search._build_chunks_from_resume("resume_a", resume)
    chunks += vector_search._build_chunks_from_resume("resume_b", resume)

    merged = vector_search._merge_chunks(chunks)

    assert len(merged) == 5
    assert all(chunk.metadata["versions"] == "resume_a,resume_b" for chunk in merged)


def test_build_index_reuses_cached_embeddings_and_writes_status(
    monkeypatch, tmp_path: Path
) -> None:
    settings = vector_search.get_settings()
    monkeypatch.setattr(
        vector_search,
        "get_settings",
        lambda: type(
            "Settings",
            (),
            {
                "vector_db_dir": tmp_path / "vector_db",
                "index_status_path": tmp_path / "vector_db" / "index_status.json",
                "embedding_provider": settings.embedding_provider,
                "resume_fs_url": "mem://",
                "jd_fs_url": "mem://",
            },
        )(),
    )
    monkeypatch.setattr(vector_search, "find_resume_versions", lambda: ["resume_a"])
    monkeypatch.setattr(
        vector_search, "load_complete_resume_as_dict", lambda version: _sample_resume()
    )

    fresh_chunks = vector_search._merge_chunks(
        vector_search._build_chunks_from_resume("resume_a", _sample_resume())
    )
    cached_chunk = fresh_chunks[0]
    fake_collection = FakeCollection(
        {
            cached_chunk.id: {
                "document": cached_chunk.text,
                "metadata": cached_chunk.metadata,
                "embedding": [0.5, 0.6],
            }
        }
    )
    monkeypatch.setattr(
        vector_search, "_get_client_and_collection", lambda: (object(), fake_collection)
    )
    fake_embeddings = FakeEmbeddings()
    monkeypatch.setattr(
        vector_search, "get_embedding_model", lambda provider=None: fake_embeddings
    )

    result = vector_search.build_index()

    assert result["exists"] is True
    assert result["entry_chunks"] == 2
    assert result["bullet_chunks"] == 3
    assert result["cached_embeddings"] == 1
    assert result["new_embeddings"] == 4
    assert len(fake_embeddings.embed_documents_calls) == 1
    assert (tmp_path / "vector_db" / "index_status.json").exists()


def test_ensure_filesystems_initialized_bootstraps_from_settings(monkeypatch) -> None:
    init_calls: list[tuple[str, str]] = []

    monkeypatch.setattr(vector_search, "is_initialized", lambda: False)
    monkeypatch.setattr(
        vector_search,
        "get_settings",
        lambda: type(
            "Settings",
            (),
            {"resume_fs_url": "mem://", "jd_fs_url": "mem://"},
        )(),
    )
    monkeypatch.setattr(
        vector_search,
        "init_filesystems",
        lambda resume_fs_url, jd_fs_url: init_calls.append((resume_fs_url, jd_fs_url)),
    )

    vector_search._ensure_filesystems_initialized()

    assert init_calls == [("mem://", "mem://")]


def test_search_entries_applies_filters_and_returns_similarity(monkeypatch) -> None:
    fake_collection = FakeCollection()
    fake_embeddings = FakeEmbeddings()

    monkeypatch.setattr(
        vector_search, "ensure_index_ready", lambda: {"auto_rebuilt": False}
    )
    monkeypatch.setattr(
        vector_search, "_get_client_and_collection", lambda: (object(), fake_collection)
    )
    monkeypatch.setattr(
        vector_search, "get_embedding_model", lambda provider=None: fake_embeddings
    )
    monkeypatch.setattr(
        vector_search,
        "get_settings",
        lambda: type("Settings", (), {"embedding_provider": "google"})(),
    )

    result = vector_search.search_entries(
        query="distributed systems",
        entry_type="experience",
        chunk_level="bullet",
        top_k=2,
    )

    assert result["request"]["entry_type"] == "experience"
    assert result["request"]["chunk_level"] == "bullet"
    assert result["result_count"] == 2
    assert len(result["results"]) == 2
    assert result["results"][0]["score"] == 0.9
    assert result["results"][0]["score_percent"] == 90.0
    assert result["results"][0]["source"]["entry_type"] == "experience"
    assert result["results"][0]["source"]["versions"] == []
    assert result["matches"] == result["results"]
    assert fake_collection.last_query is not None
    assert fake_collection.last_query["where"] == {
        "$and": [
            {"chunk_level": "bullet"},
            {"entry_type": "experience"},
        ]
    }
    assert fake_embeddings.embed_query_calls == ["distributed systems"]


def test_get_embedding_model_caches_by_provider(monkeypatch) -> None:
    class FakeGoogleEmbeddings:
        def __init__(self, *, model: str, google_api_key: str) -> None:
            self.model = model
            self.google_api_key = google_api_key

    class FakeOpenAIEmbeddings:
        def __init__(
            self,
            *,
            model: str,
            api_key: str,
            base_url: str | None = None,
            check_embedding_ctx_length: bool | None = None,
            tiktoken_enabled: bool | None = None,
        ) -> None:
            self.model = model
            self.api_key = api_key
            self.base_url = base_url
            self.check_embedding_ctx_length = check_embedding_ctx_length
            self.tiktoken_enabled = tiktoken_enabled

    monkeypatch.setenv("GOOGLE_API_KEY", "google-test-key")
    monkeypatch.setenv("OPENAI_API_KEY", "openai-test-key")
    monkeypatch.setenv("OPENAI_BASE_URL", "http://127.0.0.1:1234/v1")
    monkeypatch.setenv(
        "OPENAI_EMBEDDING_MODEL",
        "text-embedding-embedder_collection/nomic-embed-text-v2-moe",
    )
    monkeypatch.setattr(
        llm_config, "GoogleGenerativeAIEmbeddings", FakeGoogleEmbeddings
    )
    monkeypatch.setattr(llm_config, "OpenAIEmbeddings", FakeOpenAIEmbeddings)
    monkeypatch.setattr(llm_config, "_google_embeddings", None)
    monkeypatch.setattr(llm_config, "_openai_embeddings", None)

    google_first = llm_config.get_embedding_model("google")
    google_second = llm_config.get_embedding_model("google")
    openai_first = llm_config.get_embedding_model("openai")
    openai_second = llm_config.get_embedding_model("openai")

    assert google_first is google_second
    assert google_first.model == "models/gemini-embedding-001"
    assert openai_first is openai_second
    assert openai_first.model == "text-embedding-embedder_collection/nomic-embed-text-v2-moe"
    assert openai_first.base_url == "http://127.0.0.1:1234/v1"
    assert openai_first.check_embedding_ctx_length is False
    assert openai_first.tiktoken_enabled is False


def test_search_entries_returns_clear_error_when_embedding_call_fails(
    monkeypatch,
) -> None:
    class BrokenEmbeddings:
        model = "text-embedding-3-small"

        def embed_query(self, text: str) -> list[float]:
            raise TypeError("'NoneType' object is not iterable")

    monkeypatch.setattr(
        vector_search, "ensure_index_ready", lambda: {"auto_rebuilt": False}
    )
    monkeypatch.setattr(
        vector_search, "_get_client_and_collection", lambda: (object(), FakeCollection())
    )
    monkeypatch.setattr(
        vector_search, "get_embedding_model", lambda provider=None: BrokenEmbeddings()
    )
    monkeypatch.setattr(
        vector_search,
        "get_settings",
        lambda: type("Settings", (), {"embedding_provider": "openai"})(),
    )

    try:
        vector_search.search_entries(query="backend payments", chunk_level="bullet")
        assert False, "Expected RuntimeError when embedding provider fails"
    except RuntimeError as exc:
        message = str(exc)
        assert "Failed to generate query embedding" in message
        assert "provider=openai" in message


def test_build_index_returns_clear_error_when_document_embeddings_fail(
    monkeypatch, tmp_path: Path
) -> None:
    class BrokenEmbeddings:
        model = "text-embedding-3-small"

        def embed_documents(self, texts: list[str]) -> list[list[float]]:
            raise TypeError("'NoneType' object is not iterable")

    settings = vector_search.get_settings()
    monkeypatch.setattr(
        vector_search,
        "get_settings",
        lambda: type(
            "Settings",
            (),
            {
                "vector_db_dir": tmp_path / "vector_db",
                "index_status_path": tmp_path / "vector_db" / "index_status.json",
                "embedding_provider": "openai",
                "resume_fs_url": "mem://",
                "jd_fs_url": "mem://",
            },
        )(),
    )
    monkeypatch.setattr(vector_search, "find_resume_versions", lambda: ["resume_a"])
    monkeypatch.setattr(
        vector_search, "load_complete_resume_as_dict", lambda version: _sample_resume()
    )
    monkeypatch.setattr(
        vector_search, "_get_client_and_collection", lambda: (object(), FakeCollection())
    )
    monkeypatch.setattr(
        vector_search, "get_embedding_model", lambda provider=None: BrokenEmbeddings()
    )

    try:
        vector_search.build_index(force_rebuild=True)
        assert False, "Expected RuntimeError when document embedding generation fails"
    except RuntimeError as exc:
        message = str(exc)
        assert "Failed to generate document embeddings" in message
        assert "provider=openai" in message


def test_get_embedding_model_uses_openrouter_sdk_when_base_url_is_openrouter(
    monkeypatch,
) -> None:
    class FakeEmbeddingsAPI:
        def __init__(self) -> None:
            self.calls: list[dict] = []

        def generate(self, *, input, model: str):
            self.calls.append({"input": input, "model": model})
            return {
                "data": [
                    {"embedding": [0.11, 0.22]},
                    {"embedding": [0.33, 0.44]},
                ]
            }

    class FakeOpenRouterClient:
        def __init__(self, api_key: str) -> None:
            self.api_key = api_key
            self.embeddings = FakeEmbeddingsAPI()

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return None

    class FakeOpenRouterFactory:
        def __init__(self) -> None:
            self.instances: list[FakeOpenRouterClient] = []

        def __call__(self, *, api_key: str):
            client = FakeOpenRouterClient(api_key=api_key)
            self.instances.append(client)
            return client

    fake_factory = FakeOpenRouterFactory()
    fake_module = type("FakeOpenRouterModule", (), {"OpenRouter": fake_factory})()
    monkeypatch.setitem(sys.modules, "openrouter", fake_module)

    monkeypatch.setenv("OPENAI_BASE_URL", "https://openrouter.ai/api/v1")
    monkeypatch.setenv("OPENAI_EMBEDDING_MODEL", "Taurus")
    monkeypatch.setenv("OPENROUTER_API_KEY", "openrouter-test-key")
    monkeypatch.setattr(llm_config, "_openrouter_embeddings", None)
    monkeypatch.setattr(llm_config, "_openai_embeddings", None)

    model = llm_config.get_embedding_model("openai")
    vectors = model.embed_documents(["alpha", "beta"])
    query_vector = model.embed_query("gamma")

    assert vectors == [[0.11, 0.22], [0.33, 0.44]]
    assert query_vector == [0.11, 0.22]
    assert len(fake_factory.instances) == 2
    assert fake_factory.instances[0].api_key == "openrouter-test-key"
    assert fake_factory.instances[0].embeddings.calls[0] == {
        "input": ["alpha", "beta"],
        "model": "Taurus",
    }
