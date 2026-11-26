import json
import math

from app.services import ml
from app.services.features import FEATURES, build_features
from tests.factories import answers, full_flow

API = "/api/v1"


def _x(v=2):
    a = {q: answers(q, v) for q in ("gad7", "phq9", "oasis")}
    return build_features(a, {"age_band": "25-34", "sleep_hours": 5}, None)


def test_bundled_model_loads():
    m = ml.load_model()
    assert m is not None and m.meta["features"] == FEATURES


def test_estimate_shape():
    est = ml.estimate(_x(), validated_level=2)
    assert set(est["probabilities"]) == {"minimal", "mild", "moderate", "severe"}
    assert math.isclose(sum(est["probabilities"].values()), 1.0, abs_tol=1e-3)
    assert est["confidence"] == max(est["probabilities"].values())
    assert 0 < len(est["top_factors"]) <= 5
    assert all(not f["label"].startswith("gad7_") for f in est["top_factors"])  # human labels
    assert est["agrees_with_validated"] in (True, False)
    assert ml.estimate(_x(), None)["agrees_with_validated"] is None


def test_higher_answers_give_higher_estimate():
    low, high = ml.estimate(_x(0), None), ml.estimate(_x(3), None)
    assert low["composite_severity"] < high["composite_severity"]


def test_logreg_artifact(tmp_path):
    n = len(FEATURES)
    meta = {
        "model_version": "t",
        "model_type": "logreg",
        "features": FEATURES,
        "logreg": {
            "coef": [[0.1 * k] * n for k in range(4)],
            "intercept": [0] * 4,
            "mean": [1.0] * n,
            "scale": [1.0] * n,
        },
    }
    m = ml.Model(meta, tmp_path)
    proba, shap = m.predict([float("nan")] + [2.0] * (n - 1))
    assert proba.shape == (4,) and shap.shape == (4, n) and shap[0][0] == 0


def test_bad_artifacts_are_rejected(tmp_path, monkeypatch):
    import pytest

    with pytest.raises(ValueError):
        ml.Model({"model_version": "t", "model_type": "logreg", "features": ["x"]}, tmp_path)
    with pytest.raises(ValueError):
        ml.Model({"model_version": "t", "model_type": "svm", "features": FEATURES}, tmp_path)
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps({"nope": 1}))
    monkeypatch.setattr(ml, "BUNDLED", bad)
    from app.core.config import get_settings

    monkeypatch.setattr(get_settings(), "model_path", str(bad))
    ml.load_model.cache_clear()
    assert ml.load_model() is None and ml.estimate(_x(), 1) is None and ml.model_info() is None
    ml.load_model.cache_clear()


def test_full_flow_includes_ml_estimate(client):
    out = full_flow(client, context={"age_band": "25-34", "sleep_hours": 6})["result"]
    assert out["ml"]["label"] == "AI-assisted estimate"
    assert out["primary"] == "validated"
    assert out["response_quality"]["ok"] in (True, False)
    assert out["ml"]["model_version"].startswith("calma-")
