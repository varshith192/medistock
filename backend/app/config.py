"""Application configuration loaded from environment / .env."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BACKEND_DIR / ".env")


def _env(name: str, default: str = "") -> str:
    return (os.getenv(name) or default).strip()


@dataclass(frozen=True)
class Settings:
    groq_api_key: str = _env("GROQ_API_KEY")
    groq_model: str = _env("GROQ_MODEL", "openai/gpt-oss-120b")
    hindsight_base_url: str = _env("HINDSIGHT_BASE_URL", "https://api.hindsight.vectorize.io").rstrip("/")
    hindsight_api_key: str = _env("HINDSIGHT_API_KEY")
    hindsight_bank_id: str = _env("HINDSIGHT_BANK_ID", "medistock-360")
    database_path: Path = (BACKEND_DIR / _env("DATABASE_PATH", "./data/medistock.db")).resolve()
    frontend_origin: str = _env("FRONTEND_ORIGIN", "http://localhost:5173")

    @property
    def llm_configured(self) -> bool:
        return bool(self.groq_api_key)

    @property
    def hindsight_configured(self) -> bool:
        # Hindsight Cloud needs an API key; a self-hosted server on localhost does not.
        local = "localhost" in self.hindsight_base_url or "127.0.0.1" in self.hindsight_base_url
        return bool(self.hindsight_base_url) and (bool(self.hindsight_api_key) or local)


settings = Settings()
