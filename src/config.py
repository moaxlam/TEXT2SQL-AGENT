"""Central configuration — reads .env, exposes typed settings."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(override=True)

PROJECT_ROOT = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class Settings:
    # ── LLM ──────────────────────────────────────────────
    provider: str = os.getenv("LLM_PROVIDER", "groq")
    groq_api_key: str = os.getenv("GROQ_API_KEY", "")
    groq_model: str = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")
    openrouter_api_key: str = os.getenv("OPENROUTER_API_KEY", "")
    openrouter_model: str = os.getenv("OPENROUTER_MODEL", "meta-llama/openai/gpt-oss-120b")
    nvidia_api_key: str = os.getenv("NVIDIA_API_KEY", "")
    nvidia_model: str = os.getenv("NVIDIA_MODEL", "meta/llama-3.3-70b-instruct")
    max_tokens: int = int(os.getenv("MAX_TOKENS", "4096"))
    temperature: float = float(os.getenv("TEMPERATURE", "0.0"))

    # ── Database ─────────────────────────────────────────
    database_url: str = os.getenv("DATABASE_URL", f"sqlite:///{PROJECT_ROOT / 'data' / 'app.db'}")

    # ── Pipeline ─────────────────────────────────────────
    max_repair_attempts: int = int(os.getenv("MAX_REPAIR_ATTEMPTS", "3"))
    cache_enabled: bool = os.getenv("CACHE_ENABLED", "true").lower() == "true"
    schema_path: str = os.getenv("SCHEMA_PATH", str(PROJECT_ROOT / "data" / "schema.sql"))

    # ── Paths ────────────────────────────────────────────
    results_dir: str = str(PROJECT_ROOT / "results")
    cache_db: str = str(PROJECT_ROOT / "cache" / "cache.db")


settings = Settings()
