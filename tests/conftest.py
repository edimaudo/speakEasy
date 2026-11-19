from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from main import create_app


@pytest.fixture()
def client(tmp_path: Path):
    settings = Settings(
        app_secret="test-secret-that-is-long-enough",
        app_env="test",
        database_url=str(tmp_path / "test.sqlite3"),
        free_daily_sessions=2,
        retention_days=30,
        firebase_api_key="",
        firebase_project_id="",
        firebase_app_id="",
        recaptcha_site_key="",
        firebase_ai_location="global",
        firebase_ai_model="gemini-3.5-flash-lite",
        app_check_debug=True,
    )
    app = create_app(f"sqlite:///{tmp_path / 'test.sqlite3'}", settings)
    with TestClient(app) as test_client:
        yield test_client
