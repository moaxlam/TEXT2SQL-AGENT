"""Provider factory — create the right provider from config."""

from __future__ import annotations

from .base import LLMProvider
from ..config import settings


def create_provider(name: str | None = None) -> LLMProvider:
    name = (name or settings.provider).lower()

    if name == "groq":
        from .groq import GroqProvider
        return GroqProvider(api_key=settings.groq_api_key, model=settings.groq_model)

    if name == "openrouter":
        from .openrouter import OpenRouterProvider
        return OpenRouterProvider(api_key=settings.openrouter_api_key, model=settings.openrouter_model)

    if name == "nvidia":
        from .openai_compat import OpenAICompatProvider
        return OpenAICompatProvider(
            api_key=settings.nvidia_api_key,
            base_url="https://integrate.api.nvidia.com/v1",
            model=settings.nvidia_model,
        )

    raise ValueError(f"Unknown provider: {name!r}. Choose from: groq, openrouter, nvidia")
