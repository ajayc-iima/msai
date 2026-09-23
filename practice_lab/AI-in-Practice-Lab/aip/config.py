"""Model tiers, pricing, and environment settings.

A "profile" binds abstract tiers (SMALL / MAIN / LARGE) to concrete LiteLLM
model strings. Labs ask for a tier, never a model id, so switching provider is
one line in .env. Choose the profile with AIP_PROFILE.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

REPO_ROOT = Path(__file__).resolve().parent.parent

PROFILES: dict[str, dict[str, str]] = {
    "gemini": {  # generous free tier — the default for this module
        # NOTE: SMALL migrated twice on 2026-09-02 as free-tier daily buckets
        # (500 req/day for 3.5-flash-lite, 20 for 3.5-flash) were exhausted
        # mid-lab. gemini-3.1-flash-lite is the current SMALL tier: no
        # thinking tokens, JSON-clean, best measured accuracy of the three.
        "SMALL": "gemini/gemini-3.1-flash-lite",
        "MAIN": "gemini/gemini-3.5-flash",
        "LARGE": "gemini/gemini-3.7-flash",
        "EMBED": "gemini/gemini-embedding-001",
    },
    "nvidia": {  # free developer key from build.nvidia.com
        "SMALL": "nvidia_nim/meta/llama-3.1-8b-instruct",
        "MAIN": "nvidia_nim/meta/llama-3.3-70b-instruct",
        "LARGE": "nvidia_nim/meta/llama-3.3-70b-instruct",
        "EMBED": "nvidia_nim/nvidia/nv-embedqa-e5-v5",
    },
    "anthropic": {
        "SMALL": "anthropic/claude-3-5-haiku-latest",
        "MAIN": "anthropic/claude-sonnet-4-20250514",
        "LARGE": "anthropic/claude-sonnet-4-20250514",
        "EMBED": "local/BAAI/bge-small-en-v1.5",
    },
    "openai": {
        "SMALL": "openai/gpt-4.1-mini",
        "MAIN": "openai/gpt-4.1",
        "LARGE": "openai/gpt-4.1",
        "EMBED": "openai/text-embedding-3-small",
    },
    "ollama": {  # fully local, zero cost, no network
        "SMALL": "ollama/llama3.2:3b",
        "MAIN": "ollama/llama3.1:8b",
        "LARGE": "ollama/llama3.1:8b",
        "EMBED": "local/BAAI/bge-small-en-v1.5",
    },
}

# USD per 1M tokens (input, output). Estimates — re-check against the
# provider's pricing page. Models absent from this table report cost as
# "unpriced" rather than a confident zero.
PRICES_PER_MTOK: dict[str, tuple[float, float]] = {
    "gemini/gemini-3.5-flash-lite": (0.30, 2.50),
    "gemini/gemini-3.5-flash": (1.50, 9.00),
    "gemini/gemini-3.7-flash": (0.75, 3.75),   # $1.50/$7.50 from 2027-01-01
    # ESTIMATE: Google publishes no 3.1-flash-lite price page; carried at the
    # Gemini flash-lite family rate so the meter reports a number instead of
    # "unpriced". Re-check before quoting costs anywhere that matters.
    "gemini/gemini-3.1-flash-lite": (0.10, 0.40),
    "gemini/gemini-embedding-001": (0.15, 0.00),
    "anthropic/claude-3-5-haiku-latest": (0.80, 4.00),
    "anthropic/claude-sonnet-4-20250514": (3.00, 15.00),
    "openai/gpt-4.1-mini": (0.40, 1.60),
    "openai/gpt-4.1": (2.00, 8.00),
    "openai/text-embedding-3-small": (0.02, 0.00),
    "groq/llama-3.1-8b-instant": (0.05, 0.08),
    "groq/llama-3.3-70b-versatile": (0.59, 0.79),
}

# Models that are genuinely free at the margin (you own the hardware).
FREE_PREFIXES: tuple[str, ...] = ("ollama/", "local/")

# Every provider below exposes an OpenAI-compatible chat-completions endpoint
# (Gemini and Anthropic included), so one HTTP client covers them all.
# "model/..." prefix -> (base URL, env var holding the API key).
PROVIDER_BASE_URLS: dict[str, str] = {
    "gemini": "https://generativelanguage.googleapis.com/v1beta/openai",
    "openai": "https://api.openai.com/v1",
    "anthropic": "https://api.anthropic.com/v1",
    "nvidia_nim": "https://integrate.api.nvidia.com/v1",
    "groq": "https://api.groq.com/openai/v1",
    "ollama": "http://localhost:11434/v1",
}
PROVIDER_KEY_VARS: dict[str, str] = {
    "gemini": "GEMINI_API_KEY",
    "openai": "OPENAI_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
    "nvidia_nim": "NVIDIA_API_KEY",
    "groq": "GROQ_API_KEY",
    "ollama": "",
}


def _env_bool(name: str, default: bool = False) -> bool:
    return os.getenv(name, str(int(default))).strip().lower() in {"1", "true", "yes", "on"}


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, default))
    except (TypeError, ValueError):
        return default


@dataclass
class Settings:
    profile: str = field(default_factory=lambda: os.getenv("AIP_PROFILE", "gemini"))
    cache_dir: Path = field(
        default_factory=lambda: Path(os.getenv("AIP_CACHE_DIR", REPO_ROOT / ".aip_cache"))
    )
    cache_enabled: bool = field(default_factory=lambda: _env_bool("AIP_CACHE", True))
    # AIP_OFFLINE=1 -> serve only from cache; a cache miss raises instead of
    # calling the network. Guarantees a graded or demoed run costs nothing.
    offline: bool = field(default_factory=lambda: _env_bool("AIP_OFFLINE", False))
    # Hard ceiling for the whole process, in USD. Trips BudgetExceeded.
    budget_usd: float = field(default_factory=lambda: _env_float("AIP_BUDGET_USD", 2.0))
    max_retries: int = 4
    timeout_s: float = field(default_factory=lambda: _env_float("AIP_TIMEOUT_S", 60.0))
    temperature: float = field(default_factory=lambda: _env_float("AIP_TEMPERATURE", 0.0))
    trace_dir: Path = field(
        default_factory=lambda: Path(os.getenv("AIP_TRACE_DIR", REPO_ROOT / ".aip_traces"))
    )

    @property
    def models(self) -> dict[str, str]:
        if self.profile not in PROFILES:
            raise ValueError(
                f"Unknown AIP_PROFILE={self.profile!r}. "
                f"Choose one of {sorted(PROFILES)} or add your own in aip/config.py."
            )
        return PROFILES[self.profile]

    def __post_init__(self) -> None:
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.trace_dir.mkdir(parents=True, exist_ok=True)


settings = Settings()


def resolve_model(name_or_tier: str | None) -> str:
    """Turn 'SMALL' / 'MAIN' / 'LARGE' / 'EMBED' into a concrete model string.

    Anything that is not a known tier is passed through unchanged, so you can
    pin an exact model when you want to compare across providers.
    """
    if name_or_tier is None:
        return settings.models["MAIN"]
    key = name_or_tier.upper()
    return settings.models.get(key, name_or_tier)
