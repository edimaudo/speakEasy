from fastapi.testclient import TestClient


def scorecard(transcript: str, hot_take: bool = False):
    data = {
        "metrics": {
            "content": 80,
            "structure": 70,
            "deliveryPacing": 75,
            "confidence": 85,
            "hook": 60,
            "fillerControl": 90,
        },
        "annotations": [{
            "phrase": "I think we should simplify",
            "reason": "Tentative opening.",
            "replacement": "We should simplify.",
        }],
        "lineToFixQuote": "I think we should simplify",
        "lineToFixDiagnosis": "The opening is tentative.",
        "openingRewrite": "We should simplify the process.",
        "strengths": ["The recommendation is understandable."],
        "nextFocus": "Support the claim with one example.",
    }
    if hot_take:
        data.update({
            "stanceClarity": 80,
            "stanceVerdict": "You chose a side.",
            "punchierHookRewrite": "The status quo is no longer defensible.",
        })
    return data


TRANSCRIPT = "I think we should simplify the process because it reduces handoffs."


def test_root_renders_marketing_landing_page_with_a_single_product_value_proposition(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "Practise speaking." in response.text
    assert "Make your point." in response.text
    assert "Start practising" in response.text
    assert "Choose a prompt" not in response.text
    assert "Speak under the timer" not in response.text
    assert "Fix one thing and retry" not in response.text
    assert 'href="/app"' in response.text
    assert "Firebase" not in response.text
    assert "Gemini" not in response.text


def test_application_is_served_from_app_route_and_has_ai_configuration(client):
    response = client.get("/app")
    assert response.status_code == 200
    assert "SpeakEasy" in response.text
    assert "window.SPEAKEASY_CONFIG" in response.text
    assert '"firebaseReady": false' in response.text
    assert '"dailyLimit": 5' in response.text


def test_health_does_not_require_database_or_external_persistence(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "app": "speakeasy", "aiConfigured": False}


def test_stateless_scorecard_validation_recalculates_overall(client):
    response = client.post("/api/scorecard/validate", json={
        "transcript": TRANSCRIPT,
        "scorecard": scorecard(TRANSCRIPT),
        "mode": "structured",
    })
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["overallScore"] == 77.5
    assert payload["scorecard"]["overallScore"] == 77.5


def test_scorecard_validation_rejects_quote_not_present_in_transcript(client):
    invalid = scorecard(TRANSCRIPT)
    invalid["lineToFixQuote"] = "This exact quote is not present"
    response = client.post("/api/scorecard/validate", json={
        "transcript": TRANSCRIPT,
        "scorecard": invalid,
        "mode": "structured",
    })
    assert response.status_code == 422
    assert "exact quote" in response.json()["detail"]


def test_hot_take_requires_stance_metrics(client):
    invalid = scorecard(TRANSCRIPT)
    invalid.pop("stanceClarity", None)
    response = client.post("/api/scorecard/validate", json={
        "transcript": TRANSCRIPT,
        "scorecard": invalid,
        "mode": "hot-take",
    })
    assert response.status_code == 422
    assert "stanceClarity" in response.json()["detail"]


def test_scorecard_validation_rejects_cross_origin_post(client):
    response = client.post(
        "/api/scorecard/validate",
        headers={"Origin": "https://evil.example"},
        json={"transcript": TRANSCRIPT, "scorecard": scorecard(TRANSCRIPT), "mode": "structured"},
    )
    assert response.status_code == 403


def test_no_server_side_usage_or_session_persistence_endpoints(client):
    assert client.get("/api/usage").status_code == 404
    assert client.post("/api/usage/reserve").status_code == 404
    assert client.get("/api/sessions").status_code == 404
    assert client.post("/api/sessions").status_code == 404


def test_unknown_browser_route_renders_branded_404_with_real_status(client):
    response = client.get("/this-page-does-not-exist")
    assert response.status_code == 404
    assert "Page not found" in response.text
    assert "This page could not be found." in response.text
    assert 'href="/"' in response.text
    assert 'href="/static/css/styles.css"' in response.text


def test_unknown_api_route_keeps_json_404_response(client):
    response = client.get("/api/route-that-does-not-exist")
    assert response.status_code == 404
    assert response.headers["content-type"].startswith("application/json")
    assert response.json()["detail"] == "Not Found"


def test_unhandled_browser_error_renders_branded_500_without_leaking_details(client):
    def trigger_server_error():
        raise RuntimeError("private connection details")

    client.app.add_api_route("/__test/server-error", trigger_server_error, methods=["GET"])
    with TestClient(client.app, raise_server_exceptions=False) as error_client:
        response = error_client.get("/__test/server-error")

    assert response.status_code == 500
    assert "Something went wrong" in response.text
    assert "We hit a pause." in response.text
    assert "private connection details" not in response.text
    assert 'href="/"' in response.text
