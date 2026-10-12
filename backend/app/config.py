"""Application settings, loaded from environment variables (or a .env file)."""

from __future__ import annotations

import json
from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "Killette Innovations - Barndo Build Agent API"
    environment: str = "development"  # development | test | production

    # Database. SQLite by default; any SQLAlchemy URL works (e.g. postgresql+psycopg://...).
    database_url: str = "sqlite:///./data/barndo.db"

    # AES-256 key for client PII, base64-encoded 32 bytes.
    # Generate one with:  python -m app.crypto genkey
    pii_encryption_key: str = ""

    # API keys -> role. JSON object, e.g. {"admin-key-123": "admin", "phone-1": "field"}
    # Roles (least to most privilege): viewer, field, manager, admin
    api_keys: dict[str, str] = {}

    # Budget alert thresholds (percent of total budget burned).
    budget_warning_pct: float = 85.0
    budget_critical_pct: float = 100.0

    # Cloud storage for project folders: local | gdrive | dropbox
    storage_provider: str = "local"
    storage_local_root: str = "./data/storage"
    gdrive_service_account_file: str = ""
    gdrive_root_folder_id: str = ""
    dropbox_access_token: str = ""
    dropbox_root_path: str = "/Killette Projects"

    # CORS origins allowed to call the API from a browser (the website widget).
    cors_origins: list[str] = ["https://barndobible.com", "https://www.barndobible.com"]

    # ---- Website agent (barndobible.com) ----
    anthropic_api_key: str = ""
    agent_model: str = "claude-sonnet-5-5"
    agent_max_tokens: int = 1200
    anthropic_base_url: str = "https://api.anthropic.com"

    # Knowledge base pulled from the site's public WordPress REST API.
    kb_source_url: str = "https://barndobible.com"
    kb_cache_path: str = "./data/kb.json"
    kb_refresh_hours: float = 12.0
    kb_sync_on_startup: bool = True

    # Abuse / cost guards for the public endpoints.
    public_rate_limit: int = 15  # chat requests per IP ...
    public_rate_window_s: int = 600  # ... per this many seconds
    agent_daily_limit: int = 500  # total chat requests per UTC day, all visitors
    chat_max_message_chars: int = 2000
    chat_max_history: int = 12  # messages of prior conversation kept

    @field_validator("api_keys", mode="before")
    @classmethod
    def _parse_api_keys(cls, v):
        if isinstance(v, str):
            v = v.strip()
            return json.loads(v) if v else {}
        return v

    @field_validator("api_keys")
    @classmethod
    def _check_roles(cls, v: dict[str, str]):
        from app.security import ROLE_LEVELS

        bad = {r for r in v.values() if r not in ROLE_LEVELS}
        if bad:
            raise ValueError(f"Unknown role(s) in API_KEYS: {sorted(bad)}")
        return v


@lru_cache
def get_settings() -> Settings:
    return Settings()
