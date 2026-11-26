# Calma ML

Composite anxiety-severity estimate with SHAP explanations (SPEC.md section 6.2).
The ML output is a **secondary, "AI-assisted estimate"**. The validated questionnaire
score always takes priority.

## Layout

| Path | Purpose |
|---|---|
| `data/raw/` | Original datasets (gitignored). |
| `data/processed/` | Cleaned feature tables. |
| `data/README.md` | Source + licence of every dataset (added in Phase 5). |
| `notebooks/` | EDA. |
| `src/` | `synth.py`, `features.py`, `train.py`, `evaluate.py` (Phase 5). |
| `models/` | Saved artifacts. `*.joblib` is gitignored. |
| `reports/` | Metrics, calibration plots, `MODEL_CARD.md`. |

## Setup

```bash
cd ml
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
```

Nothing to train yet. That happens in Phase 5. Metrics computed on synthetic data mean
nothing clinically, and the model card must say so.
