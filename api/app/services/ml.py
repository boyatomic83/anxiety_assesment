"""ML composite estimate + explanations (SPEC.md section 6.2).

SECONDARY result, labelled "AI-assisted estimate". The validated score always takes priority.
Artifacts are plain JSON (no pickle): a metadata file plus, for XGBoost, the booster JSON.
Explanations are exact SHAP values: XGBoost's TreeSHAP (pred_contribs) or, for logistic
regression, the linear SHAP value coef * (x - mean) on the standardised features.
"""

import json
import logging
import math
from functools import lru_cache
from pathlib import Path

import numpy as np

from app.core.config import get_settings
from app.services.features import CLASSES, FEATURE_LABELS, FEATURES

log = logging.getLogger(__name__)
APP_DIR = Path(__file__).resolve().parent.parent
BUNDLED = APP_DIR / "ml_models" / "calma-model.json"


class Model:
    def __init__(self, meta: dict, base: Path):
        if meta["features"] != FEATURES:
            raise ValueError("model features do not match the feature pipeline")
        self.meta = meta
        self.version: str = meta["model_version"]
        self.kind: str = meta["model_type"]
        if self.kind == "xgboost":
            import xgboost as xgb

            self.booster = xgb.Booster()
            self.booster.load_model(str(base / meta["booster_file"]))
        elif self.kind == "logreg":
            lr = meta["logreg"]
            self.coef = np.array(lr["coef"])  # (classes, features)
            self.intercept = np.array(lr["intercept"])
            self.mean = np.array(lr["mean"])
            self.scale = np.array(lr["scale"])
        else:
            raise ValueError(f"unknown model type {self.kind}")

    def predict(self, x: list[float]) -> tuple[np.ndarray, np.ndarray]:
        """Returns (probabilities[classes], shap[classes, features])."""
        row = np.array([x], dtype=float)
        if self.kind == "xgboost":
            import xgboost as xgb

            dm = xgb.DMatrix(row, feature_names=FEATURES, missing=np.nan)
            proba = self.booster.predict(dm)[0]
            contribs = self.booster.predict(dm, pred_contribs=True)[0]  # (classes, f+1)
            return proba, contribs[:, :-1]
        z = np.where(np.isnan(row), self.mean, row)
        z = (z - self.mean) / self.scale
        logits = z @ self.coef.T + self.intercept
        e = np.exp(logits - logits.max())
        proba = (e / e.sum())[0]
        return proba, self.coef * z  # mean of z is 0, so this is the linear SHAP value


@lru_cache
def load_model() -> Model | None:
    configured = Path(get_settings().model_path)
    candidates = [configured if configured.is_absolute() else APP_DIR.parent / configured, BUNDLED]
    for path in candidates:
        if path.is_file() and path.suffix == ".json":
            try:
                return Model(json.loads(path.read_text()), path.parent)
            except Exception:
                log.exception("could not load model from %s", path)
    log.warning("no ML model available; results will show validated scores only")
    return None


def estimate(x: list[float], validated_level: int | None) -> dict | None:
    model = load_model()
    if model is None:
        return None
    proba, shap = model.predict(x)
    cls = int(np.argmax(proba))
    impacts = shap[cls]
    order = sorted(range(len(FEATURES)), key=lambda i: -abs(impacts[i]))
    top = [
        {
            "feature": FEATURES[i],
            "label": FEATURE_LABELS[FEATURES[i]],
            "impact": round(float(impacts[i]), 4),
        }
        for i in order
        if not math.isnan(x[i]) and abs(impacts[i]) > 1e-9
    ][:5]
    return {
        "composite_severity": cls,
        "composite_label": CLASSES[cls],
        "probabilities": {c: round(float(p), 4) for c, p in zip(CLASSES, proba, strict=True)},
        "confidence": round(float(proba[cls]), 4),
        "top_factors": top,
        "model_version": model.version,
        "agrees_with_validated": None if validated_level is None else cls == validated_level,
    }


def model_info() -> dict | None:
    m = load_model()
    if m is None:
        return None
    return {k: v for k, v in m.meta.items() if k not in {"logreg"}}
