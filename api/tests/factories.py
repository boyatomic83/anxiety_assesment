"""Helpers for API tests. Answers use item ids and values only."""

from app.core.config import get_settings
from app.services.questionnaires import get_questionnaire


def answers(qid: str, values: list[int] | int) -> dict[str, int]:
    q = get_questionnaire(qid)
    vals = values if isinstance(values, list) else [values] * len(q.items)
    return dict(zip(q.item_ids, vals, strict=True))


def new_session(client, context: dict | None = None, headers: dict | None = None) -> dict:
    body = {"consent": True, "consent_version": get_settings().consent_version}
    if context is not None:
        body["context"] = context
    r = client.post("/api/v1/sessions", json=body, headers=headers or {})
    assert r.status_code == 201, r.text
    return r.json()


def guest(s: dict) -> dict:
    return {"X-Session-Token": s["guest_token"]} if s.get("guest_token") else {}


def save(client, s: dict, qid: str, values, headers: dict | None = None, timings=None):
    body = {"questionnaire_id": qid, "answers": answers(qid, values)}
    if timings:
        body["item_timings"] = timings
    return client.post(
        f"/api/v1/sessions/{s['id']}/answers",
        json=body,
        headers=guest(s) if headers is None else headers,
    )


def full_flow(client, phq9_9: int = 0, context: dict | None = None, headers=None) -> dict:
    s = new_session(client, context, headers)
    h = headers or guest(s)
    assert save(client, s, "gad2", [2, 2], h).status_code == 200
    assert save(client, s, "gad7", [2, 2, 1, 1, 2, 1, 1], h).status_code == 200  # 10 Moderate
    assert save(client, s, "phq9", [1, 1, 1, 1, 1, 1, 1, 1, phq9_9], h).status_code == 200
    assert save(client, s, "oasis", [2, 2, 1, 1, 1], h).status_code == 200  # 7
    r = client.post(f"/api/v1/sessions/{s['id']}/submit", headers=h)
    assert r.status_code == 200, r.text
    return {"session": s, "headers": h, "result": r.json()}


def register(client, email: str = "user@example.com", password: str = "correct horse battery"):
    r = client.post("/api/v1/auth/register", json={"email": email, "password": password})
    assert r.status_code == 201, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}, r.json()["user"]
