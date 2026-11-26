import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "ml"))

from src.features import FEATURES  # noqa: E402
from src.synth import generate  # noqa: E402


def test_synth_shape_and_labels():
    df = generate(400, seed=1)
    assert list(df.columns[: len(FEATURES)]) == FEATURES
    assert set(df["label"].unique()) == {0, 1, 2, 3}
    assert df[[c for c in FEATURES if c.startswith("gad7")]].max().max() <= 3
    assert df[[c for c in FEATURES if c.startswith("oasis")]].max().max() <= 4
    assert df["sleep_hours"].isna().any()  # missing context is simulated


def test_synth_is_reproducible():
    assert generate(100, seed=3).equals(generate(100, seed=3))


def test_label_tracks_scores():
    df = generate(2000, seed=2)
    gad = df[[c for c in FEATURES if c.startswith("gad7")]].sum(axis=1)
    assert np.corrcoef(gad, df["label"])[0, 1] > 0.6


def test_exported_model_loads_and_predicts():
    import xgboost as xgb

    export = ROOT / "api" / "app" / "ml_models"
    meta = json.loads((export / "calma-model.json").read_text())
    assert meta["features"] == FEATURES and "SYNTHETIC" in meta["trained_on"]
    X = generate(5, seed=4)[FEATURES].to_numpy(float)
    if meta["model_type"] == "xgboost":
        booster = xgb.Booster()
        booster.load_model(str(export / meta["booster_file"]))
        proba = booster.predict(xgb.DMatrix(X, feature_names=FEATURES, missing=np.nan))
    else:
        lr = meta["logreg"]
        z = (np.where(np.isnan(X), lr["mean"], X) - lr["mean"]) / np.array(lr["scale"])
        logits = z @ np.array(lr["coef"]).T + lr["intercept"]
        proba = np.exp(logits) / np.exp(logits).sum(1, keepdims=True)
    assert proba.shape == (5, 4)
    assert np.allclose(proba.sum(1), 1.0, atol=1e-5)
