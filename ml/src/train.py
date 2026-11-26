"""Train + compare logistic regression (baseline) and XGBoost; export the winner as JSON.

Selection: highest CV macro-F1; if within 0.01, the better-calibrated model (lower ECE).
Exports to api/app/ml_models/ (shipped inside the API image, SPEC.md section 13).
"""

import json
import sys
from datetime import date
from pathlib import Path

import numpy as np
import xgboost as xgb
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import StratifiedKFold

from src.evaluate import evaluate_all, write_reports
from src.features import CLASSES, FEATURE_LABELS, FEATURES
from src.synth import generate

ROOT = Path(__file__).resolve().parents[2]
EXPORT = ROOT / "api" / "app" / "ml_models"
REPORTS = ROOT / "ml" / "reports"
SEED = 7
XGB_PARAMS = dict(objective="multi:softprob", num_class=4, max_depth=3, learning_rate=0.08,
                  subsample=0.9, colsample_bytree=0.9, min_child_weight=3, eval_metric="mlogloss",
                  seed=SEED, nthread=2)
XGB_ROUNDS = 220


class LogReg:
    """Mean-impute + standardise + multinomial LR, exportable as plain numbers."""

    def fit(self, X: np.ndarray, y: np.ndarray) -> "LogReg":
        self.mean = np.nanmean(X, axis=0)
        Z = np.where(np.isnan(X), self.mean, X)
        self.scale = Z.std(axis=0)
        self.scale[self.scale == 0] = 1.0
        self.lr = LogisticRegression(max_iter=2000, C=0.5).fit((Z - self.mean) / self.scale, y)
        return self

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        Z = np.where(np.isnan(X), self.mean, X)
        return self.lr.predict_proba((Z - self.mean) / self.scale)


class XGB:
    def fit(self, X: np.ndarray, y: np.ndarray) -> "XGB":
        dm = xgb.DMatrix(X, label=y, feature_names=FEATURES, missing=np.nan)
        self.booster = xgb.train(XGB_PARAMS, dm, num_boost_round=XGB_ROUNDS)
        return self

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        return self.booster.predict(xgb.DMatrix(X, feature_names=FEATURES, missing=np.nan))


MODELS = {"logreg": LogReg, "xgboost": XGB}


def cross_validate(X, y, groups):
    skf = StratifiedKFold(n_splits=5, shuffle=True, random_state=SEED)
    oof = {name: np.zeros((len(y), 4)) for name in MODELS}
    for train_idx, test_idx in skf.split(X, y):
        for name, cls in MODELS.items():
            oof[name][test_idx] = cls().fit(X[train_idx], y[train_idx]).predict_proba(X[test_idx])
    return {name: evaluate_all(y, p, groups, name) for name, p in oof.items()}


def main(n: int = 6000) -> dict:
    df = generate(n, SEED)
    X, y = df[FEATURES].to_numpy(float), df["label"].to_numpy(int)
    groups = df[["age_group", "gender"]]
    results = cross_validate(X, y, groups)

    lr_f1, xgb_f1 = results["logreg"]["macro_f1"], results["xgboost"]["macro_f1"]
    if abs(xgb_f1 - lr_f1) <= 0.01:
        winner = min(results, key=lambda k: results[k]["ece"])
    else:
        winner = "xgboost" if xgb_f1 > lr_f1 else "logreg"

    version = f"calma-{winner}-synth-{date.today():%Y%m%d}"
    model = MODELS[winner]().fit(X, y)
    EXPORT.mkdir(parents=True, exist_ok=True)
    meta = {
        "model_version": version,
        "model_type": winner,
        "trained_on": "SYNTHETIC data (ml/src/synth.py) - metrics are not clinically meaningful",
        "features": FEATURES,
        "feature_labels": FEATURE_LABELS,
        "classes": CLASSES,
        "cv_metrics": {
            k: {m: v for m, v in r.items() if m not in ("subgroups", "_proba")}
            for k, r in results.items()
        },
        "selected_by": "macro-F1 (ECE tie-break within 0.01)",
        "n_train": int(len(y)),
    }
    for old in EXPORT.glob("calma-*"):
        old.unlink()
    if winner == "xgboost":
        meta["booster_file"] = "calma-xgb-booster.json"
        model.booster.save_model(str(EXPORT / meta["booster_file"]))
    else:
        meta["logreg"] = {
            "coef": model.lr.coef_.tolist(), "intercept": model.lr.intercept_.tolist(),
            "mean": model.mean.tolist(), "scale": model.scale.tolist(),
        }
    (EXPORT / "calma-model.json").write_text(json.dumps(meta, indent=1))

    REPORTS.mkdir(parents=True, exist_ok=True)
    write_reports(results, winner, version, model, X, df, REPORTS)
    print(f"selected {winner}: macro-F1 LR={lr_f1:.3f} XGB={xgb_f1:.3f}; exported {version}")
    return meta


if __name__ == "__main__":
    sys.exit(0 if main() else 1)
