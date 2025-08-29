from typing import Optional
from app.core.config import get_settings

try:
    from openai import OpenAI
except Exception:  # optional dependency
    OpenAI = None  # type: ignore


def get_openai_client(api_key: Optional[str] = None, base_url: Optional[str] = None):
    settings = get_settings()
    if OpenAI is None:
        raise RuntimeError("openai package not installed. Run: pip install openai")

    resolved_key = api_key or settings.openai_api_key
    if not resolved_key:
        raise RuntimeError("OPENAI_API_KEY is not set")

    resolved_base = base_url or settings.openai_base_url
    if resolved_base:
        return OpenAI(api_key=resolved_key, base_url=resolved_base)
    return OpenAI(api_key=resolved_key)
