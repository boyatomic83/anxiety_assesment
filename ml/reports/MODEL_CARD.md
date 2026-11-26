# Model card: Calma composite severity estimate

**Version:** `calma-xgboost-synth-20261126` | **Model:** xgboost | **Status:** pipeline prototype (synthetic data)

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
- 6000 simulated respondents from `ml/src/synth.py` (seed 7): latent anxiety/depression traits
  generate GAD-7, PHQ-9 and OASIS item answers, context (age band, sleep, symptom duration,
  stressful event, caffeine) and per-item response times; ~3% careless responders.
- The label is a composite derived from the latent traits, so the task is learnable by
  construction. Real-world performance is unknown.

## Features
28 features: 21 item answers, age band, sleep hours, symptom duration, recent
stressful event, caffeine per day, mean seconds per item, share of very quick answers.
Missing context is allowed. Most influential (global mean |SHAP|): How long symptoms have lasted, OASIS item 4, OASIS item 5, GAD-7 item 3, GAD-7 item 6.

## Evaluation (stratified 5-fold CV)
| model | macro-F1 | ROC-AUC (OvR) | ECE | Brier (mean) |
|---|---|---|---|---|
| logreg | 0.759 | 0.941 | 0.014 | 0.078 |
| xgboost | 0.751 | 0.938 | 0.013 | 0.081 |

Selected **xgboost** by macro-F1 (ECE as tie-break within 0.01).
Plots: `confusion_matrix.png`, `calibration.png`, `shap_summary.png`. Raw numbers: `metrics.json`.

## Fairness: subgroup breakdown (xgboost)
| attribute | group | n | macro-F1 | accuracy |
|---|---|---|---|---|
| age_group | 18-24 | 1295 | 0.757 | 0.771 |
| age_group | 25-34 | 1673 | 0.745 | 0.760 |
| age_group | 35-44 | 1198 | 0.765 | 0.768 |
| age_group | 45-54 | 853 | 0.731 | 0.747 |
| age_group | 55-64 | 626 | 0.744 | 0.759 |
| age_group | 65+ | 355 | 0.768 | 0.789 |
| gender | female | 2814 | 0.755 | 0.765 |
| gender | male | 2818 | 0.746 | 0.760 |
| gender | non_binary | 190 | 0.769 | 0.774 |
| gender | prefer_not | 178 | 0.752 | 0.787 |

Macro-F1 range across subgroups: 0.731 to 0.769. Small groups (e.g. non-binary)
have wide uncertainty. The simulator adds no group effects, so these numbers can't reveal real
bias; re-run this analysis on real data.

## Explanations
Per-result top-5 factors are exact SHAP values (XGBoost TreeSHAP, or linear SHAP for logistic
regression), computed in the API with no extra dependency.

## Limitations
- Synthetic training data; no external validation.
- English-language item semantics only; Hindi responses are scored identically.
- Careless-responding flags are rules (identical answers, very fast, contradictory), not ML.
