"""Backend settings from environment variables."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


def _origins() -> list[str]:
    raw = os.environ.get("CRIMEX_CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000")
    return [o.strip() for o in raw.split(",") if o.strip()]


@dataclass(frozen=True)
class Settings:
    # Path to the platform YAML config; paths inside it locate data and artifacts.
    config_path: Path | None = field(
        default_factory=lambda: Path(p) if (p := os.environ.get("CRIMEX_CONFIG")) else None
    )
    cors_origins: list[str] = field(default_factory=_origins)
    api_prefix: str = "/api/v1"


def get_settings() -> Settings:
    return Settings()
