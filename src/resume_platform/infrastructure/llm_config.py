import os
from typing import Optional, Any
from dotenv import load_dotenv

try:
    from langchain_openai import OpenAIEmbeddings
except Exception:  # pragma: no cover - optional dependency at import time
    OpenAIEmbeddings = None

try:
    from langchain_google_genai import GoogleGenerativeAIEmbeddings
except Exception:  # pragma: no cover - optional dependency at import time
    GoogleGenerativeAIEmbeddings = None

# Load environment variables from .env file
load_dotenv()

# Lazy, cached clients (created on first use only)
_google_llm: Optional[Any] = None
_google_llm_think: Optional[Any] = None
_openai_llm: Optional[Any] = None
_openai_llm_think: Optional[Any] = None
_deepseek_llm: Optional[Any] = None
_deepseek_llm_think: Optional[Any] = None
_google_embeddings: Optional[Any] = None
_openai_embeddings: Optional[Any] = None
_openrouter_embeddings: Optional[Any] = None


def _chat_openai_class() -> Any:
    # Import on demand to avoid heavy module import during MCP server startup.
    from langchain_openai import ChatOpenAI

    return ChatOpenAI


def _openai_embeddings_class() -> Any:
    if OpenAIEmbeddings is not None:
        return OpenAIEmbeddings

    from langchain_openai import OpenAIEmbeddings as openai_embeddings_class

    return openai_embeddings_class


def _chat_google_class() -> Any:
    from langchain_google_genai import ChatGoogleGenerativeAI

    return ChatGoogleGenerativeAI


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


def get_llm(provider: str = "deepseek"):
    """Return a regular LLM client lazily for the given provider.

    Supported providers: 'google', 'openai', 'deepseek' (default).
    """
    provider_lc = provider.lower()
    if provider_lc == "openai":
        global _openai_llm
        if _openai_llm is None:
            chat_openai = _chat_openai_class()
            _openai_llm = chat_openai(
                model="gpt-4o",
                api_key=_require_env("OPENAI_API_KEY"),
                temperature=0.7,
                top_p=0.95,
            )
        return _openai_llm
    if provider_lc == "deepseek":
        global _deepseek_llm
        if _deepseek_llm is None:
            chat_openai = _chat_openai_class()
            _deepseek_llm = chat_openai(
                model="deepseek/deepseek-chat",
                api_key=_require_env("DEEPSEEK_API_KEY"),
                base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1"),
                temperature=0.7,
                top_p=0.95,
            )
        return _deepseek_llm
    # google (default fallback when explicitly requested)
    global _google_llm
    if _google_llm is None:
        chat_google = _chat_google_class()
        _google_llm = chat_google(
            model="gemini-2.0-flash",
            google_api_key=_require_env("GOOGLE_API_KEY"),
            temperature=0.7,
            top_p=0.95,
        )
    return _google_llm


def get_thinking_llm(provider: str = "deepseek"):
    """Return a 'thinking' LLM client lazily for the given provider."""
    provider_lc = provider.lower()
    if provider_lc == "openai":
        global _openai_llm_think
        if _openai_llm_think is None:
            chat_openai = _chat_openai_class()
            _openai_llm_think = chat_openai(
                model="gpt-4o",
                api_key=_require_env("OPENAI_API_KEY"),
                temperature=0.5,
                top_p=0.9,
            )
        return _openai_llm_think
    if provider_lc == "deepseek":
        global _deepseek_llm_think
        if _deepseek_llm_think is None:
            chat_openai = _chat_openai_class()
            _deepseek_llm_think = chat_openai(
                model="deepseek/deepseek-reasoner",
                api_key=_require_env("DEEPSEEK_API_KEY"),
                base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1"),
                temperature=0.5,
                top_p=0.9,
            )
        return _deepseek_llm_think
    # google
    global _google_llm_think
    if _google_llm_think is None:
        chat_google = _chat_google_class()
        _google_llm_think = chat_google(
            model="gemini-2.5-flash",
            google_api_key=_require_env("GOOGLE_API_KEY"),
            temperature=0.5,
            top_p=0.9,
        )
    return _google_llm_think


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
