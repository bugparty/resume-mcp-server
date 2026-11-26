"""Embedding clients for semantic search (lazy, cached per provider).

The server itself makes no chat-LLM calls: the MCP client is the LLM.
"""

import os
from typing import Optional, Any

try:
    from langchain_openai import OpenAIEmbeddings
except Exception:  # pragma: no cover - optional dependency at import time
    OpenAIEmbeddings = None

try:
    from langchain_google_genai import GoogleGenerativeAIEmbeddings
except Exception:  # pragma: no cover - optional dependency at import time
    GoogleGenerativeAIEmbeddings = None

# Lazy, cached clients (created on first use only)
_google_embeddings: Optional[Any] = None
_openai_embeddings: Optional[Any] = None
_openrouter_embeddings: Optional[Any] = None


def _openai_embeddings_class() -> Any:
    if OpenAIEmbeddings is not None:
        return OpenAIEmbeddings

    from langchain_openai import OpenAIEmbeddings as openai_embeddings_class

    return openai_embeddings_class


def _google_embeddings_class() -> Any:
    if GoogleGenerativeAIEmbeddings is not None:
        return GoogleGenerativeAIEmbeddings

    from langchain_google_genai import (
        GoogleGenerativeAIEmbeddings as google_embeddings_class,
    )

    return google_embeddings_class


def _require_env(var_name: str) -> str:
    value = os.getenv(var_name)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {var_name}")
    return value


def _is_openrouter_base_url(base_url: str | None) -> bool:
    return isinstance(base_url, str) and "openrouter.ai" in base_url.lower()


class OpenRouterEmbeddings:
    """Embedding adapter backed by the OpenRouter SDK."""

    def __init__(self, *, model: str, api_key: str) -> None:
        self.model = model
        self.api_key = api_key

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        vectors = self._generate(texts)
        if len(vectors) != len(texts):
            raise RuntimeError(
                f"OpenRouter embeddings count mismatch: expected {len(texts)}, got {len(vectors)}"
            )
        return vectors

    def embed_query(self, text: str) -> list[float]:
        vectors = self._generate([text])
        if not vectors:
            raise RuntimeError("OpenRouter embeddings returned an empty response.")
        return vectors[0]

    def _generate(self, inputs: list[str]) -> list[list[float]]:
        try:
            from openrouter import OpenRouter
        except Exception as exc:
            raise RuntimeError(
                "OpenRouter SDK is required for OPENAI_BASE_URL=openrouter.ai. "
                "Install dependency: pip install openrouter"
            ) from exc

        with OpenRouter(api_key=self.api_key) as open_router:
            response = open_router.embeddings.generate(input=inputs, model=self.model)
        data = self._extract_data(response)
        vectors: list[list[float]] = []
        for item in data:
            embedding = item.get("embedding") if isinstance(item, dict) else None
            if embedding is None and hasattr(item, "embedding"):
                embedding = getattr(item, "embedding")
            if isinstance(embedding, list):
                vectors.append(embedding)
        return vectors

    @staticmethod
    def _extract_data(response: Any) -> list[Any]:
        if isinstance(response, dict):
            return response.get("data") or []
        data = getattr(response, "data", None)
        return data or []


def get_embedding_model(provider: str = "google") -> Any:
    """Return an embedding client lazily for the given provider.

    Supported providers: 'google' (default), 'openai'.
    """

    provider_lc = provider.lower()
    if provider_lc == "openai":
        base_url = os.getenv("OPENAI_BASE_URL")
        model_name = os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")

        if _is_openrouter_base_url(base_url):
            global _openrouter_embeddings
            if _openrouter_embeddings is None:
                openrouter_key = os.getenv("OPENROUTER_API_KEY") or os.getenv(
                    "OPENAI_API_KEY"
                )
                if not openrouter_key:
                    raise RuntimeError(
                        "Missing required environment variable: OPENROUTER_API_KEY "
                        "(or OPENAI_API_KEY fallback)"
                    )
                _openrouter_embeddings = OpenRouterEmbeddings(
                    model=model_name,
                    api_key=openrouter_key,
                )
            return _openrouter_embeddings

        global _openai_embeddings
        if _openai_embeddings is None:
            openai_embeddings = _openai_embeddings_class()
            _openai_embeddings = openai_embeddings(
                model=model_name,
                api_key=_require_env("OPENAI_API_KEY"),
                base_url=base_url,
                check_embedding_ctx_length=False,
                tiktoken_enabled=False,
            )
        return _openai_embeddings

    global _google_embeddings
    if _google_embeddings is None:
        google_embeddings = _google_embeddings_class()
        _google_embeddings = google_embeddings(
            model="models/gemini-embedding-001",
            google_api_key=_require_env("GOOGLE_API_KEY"),
        )
    return _google_embeddings
