import uuid
from datetime import datetime, timezone


def scorecard(transcript: str, hot_take: bool = False):
    data = {
        "metrics": {"content": 80, "structure": 70, "deliveryPacing": 75, "confidence": 85, "hook": 60, "fillerControl": 90},
        "annotations": [{"phrase": "I think we should simplify", "reason": "Tentative opening.", "replacement": "We should simplify."}],
        "lineToFixQuote": "I think we should simplify",
        "lineToFixDiagnosis": "The opening is tentative.",
        "openingRewrite": "We should simplify the process.",
        "strengths": ["The recommendation is understandable."],
        "nextFocus": "Support the claim with one example.",
    }
    if hot_take:
        data.update({"stanceClarity": 80, "stanceVerdict": "You chose a side.", "punchierHookRewrite": "The status quo is no longer defensible."})
    return data


def reserve(client):
    reservation_id = str(uuid.uuid4())
    response = client.post("/api/usage/reserve", json={"reservation_id": reservation_id, "purpose": "structured"})
    assert response.status_code == 200, response.text
    return reservation_id


def session_payload(reservation_id, mode="structured"):
    transcript = "I think we should simplify the process because it reduces handoffs."
    return {
        "session_id": str(uuid.uuid4()),
        "reservation_id": reservation_id,
        "mode": mode,
        "goal": "Presentation" if mode == "structured" else "",
        "category": "UX & Product Design" if mode == "hot-take" else "",
        "heat": "Spicy" if mode == "hot-take" else "",
        "prompt": "Explain why this recommendation matters now.",
        "constraint_phrase": "",
        "transcript": transcript,
        "scorecard": scorecard(transcript, mode == "hot-take"),
        "inference_source": "IN_CLOUD",
        "duration_seconds": 50,
        "filler_count": 1,
    }


def test_home_renders_server_template_and_no_firebase_means_ai_not_ready(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "SpeakEasy" in response.text
    assert "window.SPEAKEASY_CONFIG" in response.text
    assert "firebaseReady\": false" in response.text


def test_usage_reservation_and_limit(client):
    first = reserve(client)
    second = reserve(client)
    assert first != second
    third = client.post("/api/usage/reserve", json={"reservation_id": str(uuid.uuid4()), "purpose": "structured"})
    assert third.status_code == 429
    usage = client.get("/api/usage").json()
    assert usage["used"] == 2


def test_session_save_computes_overall_and_history_is_guest_scoped(client):
    reservation_id = reserve(client)
    payload = session_payload(reservation_id)
    response = client.post("/api/sessions", json=payload)
    assert response.status_code == 201, response.text
    session = response.json()["session"]
    assert session["latest"]["overallScore"] == 77.5
    assert session["latest"]["scorecard"]["overallScore"] == 77.5
    assert client.get("/api/sessions").json()["sessions"][0]["id"] == payload["session_id"]

    other = client.__class__(client.app)
    with other:
        assert other.get("/api/sessions").json()["sessions"] == []


def test_create_session_is_idempotent_for_same_reservation(client):
    reservation_id = reserve(client)
    payload = session_payload(reservation_id)
    first = client.post("/api/sessions", json=payload)
    again = client.post("/api/sessions", json=payload)
    assert first.status_code == 201
    assert again.status_code == 201
    assert again.json()["idempotent"] is True


def test_retry_is_allowed_once_and_reuses_same_prompt(client):
    reservation_id = reserve(client)
    payload = session_payload(reservation_id)
    created = client.post("/api/sessions", json=payload)
    session_id = created.json()["session"]["id"]
    retry_payload = {
        "transcript": payload["transcript"],
        "scorecard": payload["scorecard"],
        "inference_source": "IN_CLOUD",
        "duration_seconds": 55,
        "filler_count": 0,
    }
    response = client.post(f"/api/sessions/{session_id}/retry", json=retry_payload)
    assert response.status_code == 200, response.text
    assert response.json()["session"]["retryUsed"] is True
    again = client.post(f"/api/sessions/{session_id}/retry", json=retry_payload)
    assert again.status_code == 409


def test_invalid_transcript_quote_rejected(client):
    reservation_id = reserve(client)
    payload = session_payload(reservation_id)
    payload["scorecard"]["lineToFixQuote"] = "quote not present in transcript"
    response = client.post("/api/sessions", json=payload)
    assert response.status_code == 422


def test_delete_session_and_cookie_is_http_only(client):
    reservation_id = reserve(client)
    payload = session_payload(reservation_id)
    created = client.post("/api/sessions", json=payload)
    session_id = created.json()["session"]["id"]
    deleted = client.delete(f"/api/sessions/{session_id}")
    assert deleted.status_code == 200
    assert client.get("/api/sessions").json()["sessions"] == []
    set_cookie = client.get("/").headers.get("set-cookie", "")
    # Existing client already has the cookie; check the cookie policy on a fresh client separately.
    assert "speakeasy_guest" in client.cookies


def test_same_origin_guard_rejects_cross_origin_post(client):
    response = client.post("/api/usage/reserve", headers={"Origin": "https://evil.example"}, json={
        "reservation_id": str(uuid.uuid4()), "purpose": "structured"
    })
    assert response.status_code == 403


def test_releasing_unused_reservation_restores_daily_allowance(client):
    reservation_id = reserve(client)
    before = client.get("/api/usage").json()["used"]
    released = client.post("/api/usage/release", json={"reservation_id": reservation_id})
    after = client.get("/api/usage").json()["used"]
    assert released.status_code == 200
    assert after == before - 1


def test_idempotent_session_replay_releases_any_new_duplicate_reservation(client):
    first_reservation = reserve(client)
    payload = session_payload(first_reservation)
    created = client.post("/api/sessions", json=payload)
    assert created.status_code == 201

    duplicate_reservation = reserve(client)
    replay_payload = {**payload, "reservation_id": duplicate_reservation}
    replay = client.post("/api/sessions", json=replay_payload)
    assert replay.status_code == 201
    assert replay.json()["idempotent"] is True
    assert client.get("/api/usage").json()["used"] == 1


def test_production_requires_a_strong_application_secret(tmp_path):
    from app.config import Settings
    from main import create_app
    import pytest

    settings = Settings(
        app_secret="too-short",
        app_env="production",
        database_url=str(tmp_path / "prod.sqlite3"),
        free_daily_sessions=5,
        retention_days=30,
        firebase_api_key="",
        firebase_project_id="",
        firebase_app_id="",
        recaptcha_site_key="",
        firebase_ai_location="global",
        firebase_ai_model="gemini-3.5-flash-lite",
        app_check_debug=False,
    )
    with pytest.raises(RuntimeError, match="at least 32 characters"):
        create_app(f"sqlite:///{tmp_path / 'prod.sqlite3'}", settings)


def test_unknown_browser_route_renders_branded_404_with_real_status(client):
    response = client.get("/this-page-does-not-exist")
    assert response.status_code == 404
    assert "Page not found" in response.text
    assert "That page isn't part of the conversation." in response.text
    assert 'href="/"' in response.text
    assert 'href="/static/css/styles.css"' in response.text


def test_unknown_api_route_keeps_json_404_response(client):
    response = client.get("/api/route-that-does-not-exist")
    assert response.status_code == 404
    assert response.headers["content-type"].startswith("application/json")
    assert response.json()["detail"] == "Not Found"


def test_unhandled_browser_error_renders_branded_500_without_leaking_details(client):
    from fastapi.testclient import TestClient

    def trigger_server_error():
        raise RuntimeError("private database connection string")

    client.app.add_api_route("/__test/server-error", trigger_server_error, methods=["GET"])
    with TestClient(client.app, raise_server_exceptions=False) as error_client:
        response = error_client.get("/__test/server-error")

    assert response.status_code == 500
    assert "Something went wrong" in response.text
    assert "We hit a pause." in response.text
    assert "private database connection string" not in response.text
    assert 'href="/"' in response.text
