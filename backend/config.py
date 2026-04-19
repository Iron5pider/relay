"""Centralized settings. Every env var flows through here — never os.environ in routes/services."""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Locate backend/.env regardless of CWD (alembic runs from repo root; uvicorn
# can run from either). The tuple lets a repo-root .env override when present.
_BACKEND_ENV = Path(__file__).resolve().parent / ".env"
_REPO_ENV = Path(__file__).resolve().parents[1] / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(str(_BACKEND_ENV), str(_REPO_ENV)),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    environment: str = "local"

    cors_allow_origins: list[str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]

    database_url: str = ""

    twilio_account_sid: str = ""
    twilio_auth_token: str = ""
    twilio_from_number: str = ""
    twilio_inbound_ivr_number: str = ""

    elevenlabs_api_key: str = ""
    elevenlabs_agent_detention_id: str = ""
    elevenlabs_agent_broker_id: str = ""
    elevenlabs_agent_driver_ivr_id: str = ""
    elevenlabs_agent_driver_checkin_id: str = ""
    elevenlabs_service_token: str = ""
    elevenlabs_webhook_secret: str = ""

    pusher_app_id: str = ""
    pusher_key: str = ""
    pusher_secret: str = ""
    pusher_cluster: str = "us3"

    relay_adapter: str = "mock"
    navpro_base_url: str = "https://api.truckerpath.com/navpro"
    navpro_credentials_path: str = "./relay-credentials.json"
    navpro_client_id: str = ""
    navpro_jwt_token: str = ""
    navpro_public_key: str = ""
    navpro_private_key: str = ""
    navpro_webhook_secret: str | None = None

    anthropic_api_key: str | None = None
    openai_api_key: str | None = None

    demo_safe_mode: bool = True
    seed_on_startup: bool = True
    batch_calls_max_concurrency: int = 8

    # Anomaly agent (Claude Sonnet 4.6 reasoning layer at the Relay ↔ NavPro seam).
    # See API_DOCS/Backend_phase_guide.md Block 4 Feature 2 +
    # /Users/girikmanchanda/.claude/plans/polished-finding-stallman.md.
    anomaly_agent_enabled: bool = True
    anomaly_agent_model: str = "claude-sonnet-4-6"
    anomaly_agent_max_tokens: int = 512
    anomaly_agent_poll_interval_hero_seconds: int = 30
    anomaly_agent_poll_interval_default_seconds: int = 60
    navpro_tracking_stale_after_minutes: int = 30
    navpro_qps_soft_cap: int = 20

    @model_validator(mode="after")
    def _fill_navpro_from_file(self) -> "Settings":
        """For any NavPro cred blank in env, fall back to relay-credentials.json.

        Env wins when set. If env is blank AND the JSON file is present, the
        JSON fills the blank. If neither source has the value, it stays "" —
        the adapter will surface a clear error on first use.
        """
        if (
            self.navpro_client_id
            and self.navpro_jwt_token
            and self.navpro_public_key
            and self.navpro_private_key
        ):
            return self

        path = Path(self.navpro_credentials_path)
        if not path.is_file():
            return self
        try:
            data = json.loads(path.read_text())
        except (OSError, json.JSONDecodeError):
            return self

        if not self.navpro_client_id:
            self.navpro_client_id = data.get("client_id", "")
        if not self.navpro_jwt_token:
            self.navpro_jwt_token = data.get("jwt_token", "")
        if not self.navpro_public_key:
            self.navpro_public_key = data.get("public_key", "")
        if not self.navpro_private_key:
            self.navpro_private_key = data.get("private_key", "")
        return self


    @property
    def database_url_async(self) -> str:
        """Return DATABASE_URL with the asyncpg driver scheme.

        Supabase gives a `postgresql://…` URL; SQLAlchemy + asyncpg needs
        `postgresql+asyncpg://…`. Idempotent — already-async URLs pass through.
        """
        url = self.database_url
        if not url:
            return ""
        if url.startswith("postgresql+asyncpg://"):
            return url
        if url.startswith("postgresql://"):
            return "postgresql+asyncpg://" + url[len("postgresql://"):]
        if url.startswith("postgres://"):  # legacy Heroku-style
            return "postgresql+asyncpg://" + url[len("postgres://"):]
        return url


settings = Settings()
