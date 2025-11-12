import os
from typing import Optional
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import ChatOpenAI

# Load environment variables from .env file
load_dotenv()

# Lazy, cached clients (created on first use only)
_google_llm: Optional[ChatGoogleGenerativeAI] = None
_google_llm_think: Optional[ChatGoogleGenerativeAI] = None
_openai_llm: Optional[ChatOpenAI] = None
_openai_llm_think: Optional[ChatOpenAI] = None
_deepseek_llm: Optional[ChatOpenAI] = None
_deepseek_llm_think: Optional[ChatOpenAI] = None


def _require_env(var_name: str) -> str:
    value = os.getenv(var_name)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {var_name}")
    return value


def get_llm(provider: str = "deepseek"):
    """Return a regular LLM client lazily for the given provider.

    Supported providers: 'google', 'openai', 'deepseek' (default).
    """
    provider_lc = provider.lower()
    if provider_lc == "openai":
        global _openai_llm
        if _openai_llm is None:
            _openai_llm = ChatOpenAI(
                model="gpt-4o",
                api_key=_require_env("OPENAI_API_KEY"),
                temperature=0.7,
                top_p=0.95,
            )
        return _openai_llm
    if provider_lc == "deepseek":
        global _deepseek_llm
        if _deepseek_llm is None:
            _deepseek_llm = ChatOpenAI(
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
        _google_llm = ChatGoogleGenerativeAI(
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
            _openai_llm_think = ChatOpenAI(
                model="gpt-4o",
                api_key=_require_env("OPENAI_API_KEY"),
                temperature=0.5,
                top_p=0.9,
            )
        return _openai_llm_think
    if provider_lc == "deepseek":
        global _deepseek_llm_think
        if _deepseek_llm_think is None:
            _deepseek_llm_think = ChatOpenAI(
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
        _google_llm_think = ChatGoogleGenerativeAI(
            model="gemini-2.5-flash",
            google_api_key=_require_env("GOOGLE_API_KEY"),
            temperature=0.5,
            top_p=0.9,
        )
    return _google_llm_think

