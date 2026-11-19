import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from main import create_app


@pytest.fixture()
def client():
    settings = Settings(
        app_env="test",
        free_daily_sessions=5,
        retention_days=30,
        firebase_api_key="",
        firebase_project_id="",
        firebase_app_id="",
        recaptcha_site_key="",
        firebase_ai_location="global",
        firebase_ai_model="gemini-3.5-flash-lite",
        app_check_debug=True,
    )
    with TestClient(create_app(settings)) as test_client:
        yield test_client
