from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    app_secret: str = os.getenv("APP_SECRET", "local-development-secret-change-before-deploy")
    app_env: str = os.getenv("APP_ENV", "development")
    database_url: str = os.getenv("DATABASE_URL", "")
    free_daily_sessions: int = int(os.getenv("FREE_DAILY_SESSIONS", "5"))
    retention_days: int = int(os.getenv("SESSION_RETENTION_DAYS", "30"))
    firebase_api_key: str = os.getenv("FIREBASE_API_KEY", "")
    firebase_project_id: str = os.getenv("FIREBASE_PROJECT_ID", "")
    firebase_app_id: str = os.getenv("FIREBASE_APP_ID", "")
    recaptcha_site_key: str = os.getenv("RECAPTCHA_ENTERPRISE_SITE_KEY", "")
    firebase_ai_location: str = os.getenv("FIREBASE_AI_LOCATION", "global")
    firebase_ai_model: str = os.getenv("FIREBASE_AI_MODEL", "gemini-3.5-flash-lite")
    app_check_debug: bool = _bool("APP_CHECK_DEBUG", default=True)

    @property
    def is_production(self) -> bool:
        return self.app_env.lower() == "production" or bool(os.getenv("VERCEL"))

    @property
    def firebase_ready(self) -> bool:
        return bool(self.firebase_api_key and self.firebase_project_id and self.firebase_app_id and self.recaptcha_site_key)

    @property
    def firebase_config(self) -> dict[str, str]:
        return {
            "apiKey": self.firebase_api_key,
            "projectId": self.firebase_project_id,
            "appId": self.firebase_app_id,
        }
