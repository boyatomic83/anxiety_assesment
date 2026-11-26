from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select

from app.core import ratelimit
from app.models import AssessmentSession, AuditLog, Result, Share, User
from tests.factories import full_flow, register

API = "/api/v1"


def test_register_login_refresh_logout(client):
    headers, user = register(client)
    assert user["role"] == "user"
    assert client.get(f"{API}/me", headers=headers).json()["email"] == "user@example.com"
    dup = client.post(
        f"{API}/auth/register", json={"email": "USER@example.com", "password": "another password"}
    )
    assert dup.status_code == 409
    bad = client.post(f"{API}/auth/login", json={"email": "user@example.com", "password": "nope"})
    assert bad.status_code == 401
    ok = client.post(
        f"{API}/auth/login", json={"email": "user@example.com", "password": "correct horse battery"}
    )
    assert ok.status_code == 200 and "calma_refresh" in ok.cookies
    ref = client.post(f"{API}/auth/refresh")
    assert ref.status_code == 200 and ref.json()["access_token"]
    assert client.post(f"{API}/auth/logout").status_code == 204
    client.cookies.clear()
    assert client.post(f"{API}/auth/refresh").status_code == 401


def test_bad_tokens(client):
    assert client.get(f"{API}/me").status_code == 401
    assert client.get(f"{API}/me", headers={"Authorization": "Bearer junk"}).status_code == 401
    client.cookies.set("calma_refresh", "junk", path="/api/v1/auth")
    assert client.post(f"{API}/auth/refresh").status_code == 401


def test_password_policy(client):
    r = client.post(f"{API}/auth/register", json={"email": "a@example.com", "password": "short"})
    assert r.status_code == 422


def test_login_is_rate_limited(client):
    ratelimit.reset()
    codes = [
        client.post(
            f"{API}/auth/login", json={"email": "x@example.com", "password": "p"}
        ).status_code
        for _ in range(11)
    ]
    assert codes[:10] == [401] * 10 and codes[10] == 429


def test_logged_in_session_history_and_settings(client):
    headers, _ = register(client)
    full_flow(client, headers=headers)
    full_flow(client, headers=headers)
    hist = client.get(f"{API}/me/history", headers=headers).json()
    assert len(hist) == 2 and hist[0]["scores"]["gad7"]["total"] == 10
    r = client.patch(f"{API}/me", json={"reminder_days": 14, "locale": "hi"}, headers=headers)
    assert r.json()["reminder_days"] == 14 and r.json()["locale"] == "hi"
    r = client.patch(f"{API}/me", json={"clear_reminder": True}, headers=headers)
    assert r.json()["reminder_days"] is None


def test_claim_guest_session(client):
    flow = full_flow(client)
    headers, _ = register(client)
    body = {"session_id": flow["session"]["id"], "guest_token": "wrong"}
    assert client.post(f"{API}/me/sessions/claim", json=body, headers=headers).status_code == 404
    body["guest_token"] = flow["session"]["guest_token"]
    assert client.post(f"{API}/me/sessions/claim", json=body, headers=headers).status_code == 204
    assert len(client.get(f"{API}/me/history", headers=headers).json()) == 1
    # Guest token no longer works once claimed.
    rid = flow["result"]["id"]
    assert client.get(f"{API}/results/{rid}", headers=flow["headers"]).status_code == 404
    assert client.get(f"{API}/results/{rid}", headers=headers).status_code == 200


def test_export_and_delete_my_data(client, db):
    headers, _ = register(client)
    full_flow(client, headers=headers, context={"age_band": "25-34"})
    data = client.get(f"{API}/me/export", headers=headers).json()
    assert data["account"]["email"] == "user@example.com"
    assert data["sessions"][0]["responses"]["gad7"]["gad7_1"] == 2
    assert data["sessions"][0]["context"] == {"age_band": "25-34"}
    assert client.delete(f"{API}/me", headers=headers).status_code == 204
    assert db.scalar(select(func.count()).select_from(User)) == 0
    assert db.scalar(select(func.count()).select_from(AssessmentSession)) == 0
    assert db.scalar(select(func.count()).select_from(Result)) == 0


def _make_clinician(client, db, email="doc@example.com"):
    headers, _ = register(client, email)
    db.execute(User.__table__.update().where(User.email == email).values(role="clinician"))
    db.commit()
    return headers


def test_sharing_with_a_clinician(client, db):
    patient, _ = register(client)
    calm = full_flow(client, headers=patient)["result"]
    crisis = full_flow(client, headers=patient, phq9_9=2)["result"]
    doc = _make_clinician(client, db)

    # Guests and plain users cannot use clinician views.
    assert client.get(f"{API}/clinician/patients", headers=patient).status_code == 403
    codes = [
        client.post(f"{API}/results/{r['id']}/share", headers=patient).json()["code"]
        for r in (calm, crisis)
    ]
    for code in codes:
        r = client.post(f"{API}/clinician/shares/redeem", json={"code": code.lower()}, headers=doc)
        assert r.status_code == 200

    patients = client.get(f"{API}/clinician/patients", headers=doc).json()
    assert [p["flagged"] for p in patients] == [True, False]  # flagged first
    flagged = client.get(f"{API}/clinician/flagged", headers=doc).json()
    assert [p["result_id"] for p in flagged] == [crisis["id"]]
    view = client.get(f"{API}/clinician/results/{crisis['id']}", headers=doc)
    assert view.status_code == 200 and view.json()["crisis"] is not None
    assert client.get(f"{API}/clinician/results/{'0' * 32}", headers=doc).status_code == 404
    csv = client.get(f"{API}/clinician/export.csv", headers=doc)
    assert csv.headers["content-type"].startswith("text/csv") and "gad7" in csv.text

    other = _make_clinician(client, db, "doc2@example.com")
    r = client.post(f"{API}/clinician/shares/redeem", json={"code": codes[0]}, headers=other)
    assert r.status_code == 404  # already redeemed by another clinician
    assert client.get(f"{API}/clinician/patients", headers=other).json() == []

    actions = {a.action for a in db.scalars(select(AuditLog))}
    assert {
        "share.redeem",
        "clinician.list_patients",
        "clinician.view_result",
        "clinician.export",
        "clinician.list_flagged",
    } <= actions


def test_expired_share_code(client, db):
    patient, _ = register(client)
    result = full_flow(client, headers=patient)["result"]
    code = client.post(f"{API}/results/{result['id']}/share", headers=patient).json()["code"]
    db.execute(Share.__table__.update().values(expires_at=datetime.now(UTC) - timedelta(days=1)))
    db.commit()
    doc = _make_clinician(client, db)
    r = client.post(f"{API}/clinician/shares/redeem", json={"code": code}, headers=doc)
    assert r.status_code == 404


def test_guest_cannot_share(client):
    flow = full_flow(client)
    r = client.post(f"{API}/results/{flow['result']['id']}/share", headers=flow["headers"])
    assert r.status_code == 401


def test_admin_endpoints(client, db):
    admin, _ = register(client, "admin@example.com")
    db.execute(
        User.__table__.update().where(User.email == "admin@example.com").values(role="admin")
    )
    db.commit()
    register(client, "doc@example.com")
    r = client.post(
        f"{API}/admin/users/role",
        json={"email": "doc@example.com", "role": "clinician"},
        headers=admin,
    )
    assert r.json()["role"] == "clinician"
    r = client.post(
        f"{API}/admin/users/role",
        json={"email": "nobody@example.com", "role": "clinician"},
        headers=admin,
    )
    assert r.status_code == 404
    audit = client.get(f"{API}/admin/audit", headers=admin).json()
    assert {"admin.set_role", "admin.view_audit"} <= {a["action"] for a in audit}
    assert "active" in client.get(f"{API}/admin/models", headers=admin).json()
    assert len(client.get(f"{API}/admin/questionnaires", headers=admin).json()) == 5
    user, _ = register(client, "plain@example.com")
    assert client.get(f"{API}/admin/audit", headers=user).status_code == 403
