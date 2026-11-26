from sqlalchemy import select

from app.core.config import get_settings
from app.models import Response
from tests.factories import answers, full_flow, guest, new_session, save

API = "/api/v1"


def test_consent_is_required(client):
    r = client.post(f"{API}/sessions", json={"consent": False, "consent_version": "x"})
    assert r.status_code == 422
    r = client.post(f"{API}/sessions", json={"consent": True, "consent_version": "old"})
    assert r.status_code == 409


def test_guest_session_gets_token_and_expiry(client):
    s = new_session(client)
    assert s["guest_token"] and s["expires_at"]
    assert s["consent_version"] == get_settings().consent_version


def test_session_access_needs_the_token(client):
    s = new_session(client)
    for headers in ({}, {"X-Session-Token": "wrong"}):
        r = save(client, s, "gad7", 0, headers)
        assert r.status_code == 404
    assert save(client, s, "gad7", 0).status_code == 200


def test_autosave_merges_partial_answers(client):
    s = new_session(client)
    url = f"{API}/sessions/{s['id']}/answers"
    r = client.post(
        url, json={"questionnaire_id": "gad7", "answers": {"gad7_1": 1}}, headers=guest(s)
    )
    assert r.json() == {"questionnaire_id": "gad7", "saved_items": 1, "complete": False}
    rest = {k: 0 for k in answers("gad7", 0) if k != "gad7_1"}
    r = client.post(url, json={"questionnaire_id": "gad7", "answers": rest}, headers=guest(s))
    assert r.json()["complete"] is True


def test_invalid_answers_rejected(client):
    s = new_session(client)
    url = f"{API}/sessions/{s['id']}/answers"
    for body, code in [
        ({"questionnaire_id": "nope", "answers": {}}, 404),
        ({"questionnaire_id": "gad7", "answers": {"gad7_99": 1}}, 422),
        ({"questionnaire_id": "gad7", "answers": {"gad7_1": 7}}, 422),
    ]:
        assert client.post(url, json=body, headers=guest(s)).status_code == code


def test_answers_are_encrypted_at_rest(client, db):
    s = new_session(client)
    save(client, s, "gad7", [3, 2, 1, 0, 3, 2, 1])
    stored = db.scalar(select(Response)).answers_encrypted
    assert "gad7_1" not in stored and stored.startswith("gAAAA")


def test_full_submit_returns_validated_scores(client):
    out = full_flow(client)["result"]
    assert out["primary"] == "validated"
    assert out["flagged"] is False and out["crisis"] is None
    assert out["scores"]["gad7"]["total"] == 10 and out["scores"]["gad7"]["band"] == "Moderate"
    assert out["scores"]["phq9"]["total"] == 8
    assert out["scores"]["oasis"]["total"] == 7
    assert "gad2" not in out["scores"]  # covered by the full GAD-7
    assert "screening tool, not a diagnosis" in out["disclaimer"]


def test_gad2_only_submit(client):
    s = new_session(client)
    save(client, s, "gad2", [1, 1])
    out = client.post(f"{API}/sessions/{s['id']}/submit", headers=guest(s)).json()
    assert out["scores"]["gad2"]["band"] == "Negative screen"
    assert out["ml"] is None


def test_phq9_item_9_flags_and_shows_helplines(client):
    flow = full_flow(client, phq9_9=1)
    out = flow["result"]
    assert out["flagged"] is True
    numbers = [h.get("number") for h in out["crisis"]["helplines"]]
    assert "14416" in numbers and "112" in numbers
    # Never blocks results: they are still returned and retrievable.
    assert out["scores"]["phq9"]["total"] == 9
    r = client.get(f"{API}/results/{out['id']}", headers=flow["headers"])
    assert r.status_code == 200 and r.json()["flagged"] is True


def test_crisis_free_text_flags(client):
    out = full_flow(client, context={"free_text": "Some days I want to die."})["result"]
    assert out["flagged"] is True


def test_safety_runs_before_scoring_and_ml(client, monkeypatch):
    from app.services import assessment

    calls: list[str] = []
    real_check, real_score, real_est = (
        assessment.safety.check,
        assessment.score,
        assessment.ml.estimate,
    )
    monkeypatch.setattr(
        assessment.safety, "check", lambda *a: calls.append("safety") or real_check(*a)
    )
    monkeypatch.setattr(assessment, "score", lambda *a: calls.append("score") or real_score(*a))
    monkeypatch.setattr(assessment.ml, "estimate", lambda *a: calls.append("ml") or real_est(*a))
    full_flow(client)
    assert calls[0] == "safety"
    assert calls.index("ml") > max(i for i, c in enumerate(calls) if c == "score")


def test_incomplete_questionnaire_cannot_be_submitted(client):
    s = new_session(client)
    client.post(
        f"{API}/sessions/{s['id']}/answers",
        json={"questionnaire_id": "gad7", "answers": {"gad7_1": 1}},
        headers=guest(s),
    )
    r = client.post(f"{API}/sessions/{s['id']}/submit", headers=guest(s))
    assert r.status_code == 422 and "missing" in r.json()["detail"]


def test_empty_session_cannot_be_submitted(client):
    s = new_session(client)
    assert client.post(f"{API}/sessions/{s['id']}/submit", headers=guest(s)).status_code == 422


def test_submitted_session_is_locked_and_idempotent(client):
    flow = full_flow(client)
    s, h = flow["session"], flow["headers"]
    assert save(client, s, "gad7", 0, h).status_code == 409
    assert client.put(f"{API}/sessions/{s['id']}/context", json={}, headers=h).status_code == 409
    again = client.post(f"{API}/sessions/{s['id']}/submit", headers=h).json()
    assert again["id"] == flow["result"]["id"]


def test_context_update_merges(client):
    s = new_session(client, {"age_band": "25-34"})
    r = client.put(
        f"{API}/sessions/{s['id']}/context",
        json={"sleep_hours": 6.5, "stressful_event": True},
        headers=guest(s),
    )
    assert r.status_code == 204
    r = client.put(f"{API}/sessions/{s['id']}/context", json={"bogus": 1}, headers=guest(s))
    assert r.status_code == 422


def test_result_pdf(client):
    flow = full_flow(client, phq9_9=2)
    r = client.get(f"{API}/results/{flow['result']['id']}/pdf", headers=flow["headers"])
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/pdf"
    assert r.content.startswith(b"%PDF")


def test_result_requires_access(client):
    flow = full_flow(client)
    assert client.get(f"{API}/results/{flow['result']['id']}").status_code == 404
    other = new_session(client)
    r = client.get(f"{API}/results/{flow['result']['id']}", headers=guest(other))
    assert r.status_code == 404


def test_questionnaire_endpoints(client):
    listing = client.get(f"{API}/questionnaires").json()
    assert {q["id"] for q in listing} == {"gad2", "gad7", "phq9", "oasis", "dass21"}
    detail = client.get(f"{API}/questionnaires/gad7").json()
    assert len(detail["items"]) == 7 and detail["language"] == "en"
    assert all(i["text"] for i in detail["items"])
    assert client.get(f"{API}/questionnaires/nope").status_code == 404


def test_helplines_endpoint(client):
    india = client.get(f"{API}/helplines").json()
    assert india["country"] == "India"
    other = client.get(f"{API}/helplines?country=GB").json()
    assert other["country"] == "International"


def test_security_headers(client):
    r = client.get(f"{API}/health")
    assert r.headers["x-content-type-options"] == "nosniff"
    assert r.headers["cache-control"] == "no-store"
