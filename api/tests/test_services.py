from datetime import UTC, datetime, timedelta

import pytest

from app.core.encryption import DecryptionError, decrypt_json, encrypt_json
from app.core.security import TokenError, create_token, decode_token, hash_password, verify_password
from app.models import AssessmentSession, Result, User
from app.services import features, jobs, safety
from app.services.report import build_pdf
from tests.factories import answers

# ---------- safety ----------


@pytest.mark.parametrize(
    "text",
    [
        "I want to die",
        "thinking about SUICIDE",
        "I might hurt myself",
        "I don’t want to live",
        "मैं आत्महत्या के बारे में सोचता हूँ",
    ],
)
def test_crisis_keywords_detected(text):
    assert safety.free_text_has_crisis_language(text)


@pytest.mark.parametrize("text", [None, "", "I feel tired", "my skills improved", "die-cast car"])
def test_ordinary_text_not_flagged(text):
    assert not safety.free_text_has_crisis_language(text)


def test_phq9_item_9_threshold():
    assert not safety.check({"phq9": answers("phq9", 0)}, None).flagged
    r = safety.check({"phq9": {**answers("phq9", 0), "phq9_9": 1}}, None)
    assert r.flagged and r.reasons == ["item:phq9_9"]
    r = safety.check({"gad7": answers("gad7", 3)}, "I want to die")
    assert r.reasons == ["free_text"]


# ---------- encryption / security ----------


def test_encryption_round_trip():
    token = encrypt_json({"a": 1, "t": "नमस्ते"})
    assert decrypt_json(token) == {"a": 1, "t": "नमस्ते"}
    assert decrypt_json(None) is None
    with pytest.raises(DecryptionError):
        decrypt_json("not-a-token")


def test_passwords_and_tokens():
    h = hash_password("secret value 123")
    assert verify_password("secret value 123", h) and not verify_password("x", h)
    assert not verify_password("x", "not-a-hash")
    import uuid

    uid = uuid.uuid4()
    t = create_token(uid, "user", "access")
    assert decode_token(t, "access")["sub"] == str(uid)
    with pytest.raises(TokenError):
        decode_token(t, "refresh")
    with pytest.raises(TokenError):
        decode_token("garbage", "access")


# ---------- features / response quality ----------


def full_answers(v=1):
    return {q: answers(q, v) for q in ("gad7", "phq9", "oasis")}


def test_feature_vector_shape_and_encoding():
    x = features.build_features(
        full_answers(2),
        {
            "age_band": "25-34",
            "sleep_hours": 20,
            "symptom_duration": "1-6m",
            "stressful_event": True,
            "caffeine_cups": 15,
        },
        {"gad7_1": 1.0, "gad7_2": 3.0},
    )
    row = dict(zip(features.FEATURES, x, strict=True))
    assert len(x) == len(features.FEATURES) == 28
    assert row["gad7_1"] == 2 and row["age_band"] == 1 and row["sleep_hours"] == 14
    assert row["symptom_duration"] == 2 and row["stressful_event"] == 1.0
    assert row["caffeine_cups"] == 10 and row["mean_item_seconds"] == 2.0
    assert row["fast_item_ratio"] == 0.5


def test_missing_context_is_nan():
    import math

    x = features.build_features(full_answers(), None, None)
    row = dict(zip(features.FEATURES, x, strict=True))
    assert all(math.isnan(row[f]) for f in features.CONTEXT_FEATURES)
    assert features.has_required(full_answers()) and not features.has_required({"gad7": {}})


def test_response_quality_flags():
    a = full_answers(1)
    assert features.response_quality(a, {f"x{i}": 5.0 for i in range(10)})["flags"] == [
        "identical_answers"
    ]
    mixed = {**a, "gad7": answers("gad7", [3, 3, 3, 3, 3, 0, 0]), "oasis": answers("oasis", 0)}
    q = features.response_quality(mixed, {f"x{i}": 0.5 for i in range(10)})
    assert q["flags"] == ["very_fast", "contradictory"] and not q["ok"]
    calm = {**a, "gad7": answers("gad7", [1, 0, 1, 0, 1, 0, 1])}
    assert features.response_quality(calm, None)["ok"]


# ---------- jobs ----------


def test_purge_guest_sessions(db):
    now = datetime.now(UTC)
    user = User(email="u@example.com", password_hash="x")
    db.add_all(
        [
            user,
            AssessmentSession(consent_version="v", started_at=now - timedelta(hours=25)),
            AssessmentSession(consent_version="v", started_at=now - timedelta(hours=1)),
        ]
    )
    db.flush()
    db.add(
        AssessmentSession(consent_version="v", user_id=user.id, started_at=now - timedelta(days=30))
    )
    db.commit()
    assert jobs.purge_guest_sessions(db, now) == 1
    assert db.query(AssessmentSession).count() == 2


def test_reminders(db, monkeypatch, caplog):
    now = datetime.now(UTC)
    user = User(email="u@example.com", password_hash="x", reminder_days=14)
    quiet = User(email="q@example.com", password_hash="x")
    db.add_all([user, quiet])
    db.flush()
    for u in (user, quiet):
        s = AssessmentSession(consent_version="v", user_id=u.id)
        db.add(s)
        db.flush()
        db.add(Result(session_id=s.id, scores_json={}, created_at=now - timedelta(days=20)))
    db.commit()
    assert [u.email for u in jobs.due_reminders(db, now)] == ["u@example.com"]
    assert jobs.send_reminders(db, now) == 1  # SMTP not configured: logged, marked as reminded
    assert jobs.due_reminders(db, now) == []

    sent = []

    class FakeSMTP:
        def __init__(self, *a, **k):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def starttls(self):
            pass

        def login(self, *a):
            sent.append("login")

        def send_message(self, m):
            sent.append(m["To"])

    from app.core.config import get_settings

    monkeypatch.setattr(get_settings(), "smtp_host", "smtp.test")
    monkeypatch.setattr(get_settings(), "email_from", "calma@example.com")
    monkeypatch.setattr(jobs.smtplib, "SMTP", FakeSMTP)
    later = now + timedelta(days=30)
    assert jobs.send_reminders(db, later) == 1 and sent == ["u@example.com"]


# ---------- report ----------


def test_pdf_with_ml_and_crisis():
    scores = {
        "gad7": {"total": 12, "band": "Moderate", "level": 2, "subscales": {}},
        "dass21": {
            "total": 20,
            "band": None,
            "level": None,
            "subscales": {"anxiety": {"score": 10, "band": "Moderate", "level": 2}},
        },
    }
    ml = {
        "composite_label": "moderate",
        "confidence": 0.71,
        "model_version": "test",
        "top_factors": [
            {"label": "GAD-7 item 2", "impact": 0.4},
            {"label": "Sleep hours", "impact": -0.1},
        ],
    }
    helplines = safety.helplines_for("IN")
    pdf = build_pdf(scores, ml, True, helplines, datetime.now(UTC))
    assert pdf.startswith(b"%PDF") and len(pdf) > 1000
