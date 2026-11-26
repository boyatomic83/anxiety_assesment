"""Evaluation + reports: macro-F1, ROC-AUC (OvR), confusion matrix, calibration (ECE),
subgroup breakdown by age band and gender, SHAP summary, and the model card."""

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from sklearn.metrics import brier_score_loss, confusion_matrix, f1_score, roc_auc_score  # noqa: E402

from src.features import CLASSES, FEATURE_LABELS, FEATURES  # noqa: E402


def ece(y: np.ndarray, proba: np.ndarray, bins: int = 10) -> float:
    """Expected calibration error of the top-class confidence."""
    conf, pred = proba.max(1), proba.argmax(1)
    edges = np.linspace(0, 1, bins + 1)
    total = 0.0
    for lo, hi in zip(edges[:-1], edges[1:], strict=True):
        m = (conf > lo) & (conf <= hi)
        if m.any():
            total += m.mean() * abs((pred[m] == y[m]).mean() - conf[m].mean())
    return float(total)


def evaluate_all(y, proba, groups, name) -> dict:
    pred = proba.argmax(1)
    out = {
        "model": name,
        "macro_f1": float(f1_score(y, pred, average="macro")),
        "roc_auc_ovr": float(roc_auc_score(y, proba, multi_class="ovr")),
        "ece": ece(y, proba),
        "brier_mean": float(np.mean([brier_score_loss(y == k, proba[:, k]) for k in range(4)])),
        "confusion_matrix": confusion_matrix(y, pred, labels=range(4)).tolist(),
        "subgroups": {},
    }
    for col in groups.columns:
        out["subgroups"][col] = {}
        for value in sorted(groups[col].unique()):
            m = (groups[col] == value).to_numpy()
            out["subgroups"][col][value] = {
                "n": int(m.sum()),
                "macro_f1": float(f1_score(y[m], pred[m], average="macro")),
                "accuracy": float((y[m] == pred[m]).mean()),
            }
    out["_proba"] = proba  # dropped before serialising
    return out


def _plots(results, y, winner, reports: Path) -> None:
    cm = np.array(results[winner]["confusion_matrix"])
    fig, ax = plt.subplots(figsize=(4.5, 4))
    ax.imshow(cm, cmap="Greens")
    for i in range(4):
        for j in range(4):
            ax.text(j, i, cm[i, j], ha="center", va="center", fontsize=9)
    ax.set_xticks(range(4), CLASSES, rotation=30)
    ax.set_yticks(range(4), CLASSES)
    ax.set_xlabel("predicted")
    ax.set_ylabel("synthetic label")
    ax.set_title(f"Confusion matrix ({winner}, 5-fold CV)")
    fig.tight_layout()
    fig.savefig(reports / "confusion_matrix.png", dpi=120)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(4.5, 4))
    ax.plot([0, 1], [0, 1], "--", color="#999")
    for name, r in results.items():
        p = r["_proba"]
        conf, hit = p.max(1), (p.argmax(1) == y)
        edges = np.linspace(0, 1, 11)
        xs, ys = [], []
        for lo, hi in zip(edges[:-1], edges[1:], strict=True):
            m = (conf > lo) & (conf <= hi)
            if m.sum() >= 10:
                xs.append(conf[m].mean())
                ys.append(hit[m].mean())
        ax.plot(xs, ys, "o-", label=f"{name} (ECE {r['ece']:.3f})")
    ax.set_xlabel("confidence")
    ax.set_ylabel("accuracy")
    ax.set_title("Calibration (top class)")
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(reports / "calibration.png", dpi=120)
    plt.close(fig)


def _global_importance(model, winner, X) -> list[tuple[str, float]]:
    if winner == "xgboost":
        try:
            import shap

            sv = shap.TreeExplainer(model.booster).shap_values(X[:1000])
            arr = np.abs(np.array(sv))
            imp = arr.mean(axis=tuple(i for i in range(arr.ndim) if arr.shape[i] != len(FEATURES)))
        except Exception:  # shap/xgboost version mismatch: use XGBoost's own TreeSHAP
            import xgboost as xgb

            c = model.booster.predict(xgb.DMatrix(X[:1000], feature_names=FEATURES,
                                                  missing=np.nan), pred_contribs=True)
            imp = np.abs(c[:, :, :-1]).mean(axis=(0, 1))
    else:
        Z = np.where(np.isnan(X), model.mean, X)
        Z = (Z - model.mean) / model.scale
        imp = np.abs(model.lr.coef_[None, :, :] * Z[:, None, :]).mean(axis=(0, 1))
    return sorted(zip(FEATURES, imp.tolist(), strict=True), key=lambda t: -t[1])


def write_reports(results, winner, version, model, X, df, reports: Path) -> None:
    y = df["label"].to_numpy(int)
    _plots(results, y, winner, reports)
    importance = _global_importance(model, winner, X)
    fig, ax = plt.subplots(figsize=(6, 4.5))
    top = importance[:12][::-1]
    ax.barh([FEATURE_LABELS[f] for f, _ in top], [v for _, v in top], color="#5b8a72")
    ax.set_title("Mean |SHAP| (global importance)")
    fig.tight_layout()
    fig.savefig(reports / "shap_summary.png", dpi=120)
    plt.close(fig)

    clean = {k: {m: v for m, v in r.items() if m != "_proba"} for k, r in results.items()}
    (reports / "metrics.json").write_text(json.dumps(
        {"selected": winner, "model_version": version, "results": clean,
         "global_importance": importance}, indent=2))
    (reports / "MODEL_CARD.md").write_text(_model_card(clean, winner, version, importance, len(y)))


def _model_card(results, winner, version, importance, n) -> str:
    def row(name):
        r = results[name]
        return (f"| {name} | {r['macro_f1']:.3f} | {r['roc_auc_ovr']:.3f} | {r['ece']:.3f} "
                f"| {r['brier_mean']:.3f} |")

    sub_lines = []
    for col, values in results[winner]["subgroups"].items():
        for v, m in values.items():
            sub_lines.append(f"| {col} | {v} | {m['n']} | {m['macro_f1']:.3f} | {m['accuracy']:.3f} |")
    f1s = [m["macro_f1"] for vals in results[winner]["subgroups"].values() for m in vals.values()]
    top = ", ".join(FEATURE_LABELS[f] for f, _ in importance[:5])
    return f"""# Model card: Calma composite severity estimate

**Version:** `{version}` | **Model:** {winner} | **Status:** pipeline prototype (synthetic data)

> **Metrics below come from SYNTHETIC data and mean nothing clinically.** They only show that
> the training, evaluation and serving pipeline works end to end. Do not use this model to
> inform care until it is retrained and validated on a real, openly licensed dataset
> (Phase B, SPEC.md section 6.2), with its source and licence recorded in `ml/data/README.md`.

## Intended use
- A **secondary**, explainable "AI-assisted estimate" (minimal / mild / moderate / severe) shown
  next to the validated questionnaire scores. The validated scores always take priority; the UI
  shows both when they disagree.
- Not a diagnosis. Not for treatment decisions. Not for use without the validated scores.

## Data
- {n} simulated respondents from `ml/src/synth.py` (seed 7): latent anxiety/depression traits
  generate GAD-7, PHQ-9 and OASIS item answers, context (age band, sleep, symptom duration,
  stressful event, caffeine) and per-item response times; ~3% careless responders.
- The label is a composite derived from the latent traits, so the task is learnable by
  construction. Real-world performance is unknown.

## Features
{len(FEATURES)} features: 21 item answers, age band, sleep hours, symptom duration, recent
stressful event, caffeine per day, mean seconds per item, share of very quick answers.
Missing context is allowed. Most influential (global mean |SHAP|): {top}.

## Evaluation (stratified 5-fold CV)
| model | macro-F1 | ROC-AUC (OvR) | ECE | Brier (mean) |
|---|---|---|---|---|
{row("logreg")}
{row("xgboost")}

Selected **{winner}** by macro-F1 (ECE as tie-break within 0.01).
Plots: `confusion_matrix.png`, `calibration.png`, `shap_summary.png`. Raw numbers: `metrics.json`.

## Fairness: subgroup breakdown ({winner})
| attribute | group | n | macro-F1 | accuracy |
|---|---|---|---|---|
{chr(10).join(sub_lines)}

Macro-F1 range across subgroups: {min(f1s):.3f} to {max(f1s):.3f}. Small groups (e.g. non-binary)
have wide uncertainty. The simulator adds no group effects, so these numbers can't reveal real
bias; re-run this analysis on real data.

## Explanations
Per-result top-5 factors are exact SHAP values (XGBoost TreeSHAP, or linear SHAP for logistic
regression), computed in the API with no extra dependency.

## Limitations
- Synthetic training data; no external validation.
- English-language item semantics only; Hindi responses are scored identically.
- Careless-responding flags are rules (identical answers, very fast, contradictory), not ML.
"""
