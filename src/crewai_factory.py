"""Provider-agnostic CrewAI LLM factory.

Converts the active provider config into a CrewAI LLM object.
Provider-specific logic is ONLY in this file.
All other CrewAI code receives a generic LLM.
"""
from crewai import LLM
from .config import settings


def create_crewai_llm() -> LLM:
    """Create a CrewAI LLM from the active provider configuration.

    Reads LLM_PROVIDER, model, API key from settings.
    No provider names hard-coded outside this function.

    Supported providers:
        groq       - uses OpenAI-compatible endpoint (avoids litellm cache_breakpoint issue)
        openrouter - uses OpenAI-compatible endpoint
        nvidia     - uses OpenAI-compatible endpoint
    """
    provider = settings.provider

    if provider == "groq":
        # Use OpenAI-compatible endpoint to avoid litellm cache_breakpoint error
        return LLM(
            model=f"openai/{settings.groq_model}",
            api_key=settings.groq_api_key,
            base_url="https://api.groq.com/openai/v1",
        )

    if provider == "openrouter":
        return LLM(
            model=f"openai/{settings.openrouter_model}",
            api_key=settings.openrouter_api_key,
            base_url="https://openrouter.ai/api/v1",
        )

    if provider == "nvidia":
        return LLM(
            model=f"openai/{settings.nvidia_model}",
            api_key=settings.nvidia_api_key,
            base_url="https://integrate.api.nvidia.com/v1",
        )

    raise ValueError(
        f"Unknown provider: {provider!r}. "
        f"Set LLM_PROVIDER to groq, openrouter, or nvidia."
    )
