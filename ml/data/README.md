# Datasets

| Phase | Dataset | Source | Licence | Status |
|---|---|---|---|---|
| A | Synthetic respondents (`src/synth.py`, seed 7) | generated | n/a | **in use**: metrics are not clinically meaningful |
| B | Real, openly licensed data with GAD-7 and/or DASS items | _to choose_ (Kaggle / OSF / published supplementary data) | _record here_ | not started |

Rules:
- Raw downloads go in `data/raw/` (gitignored). Processed tables go in `data/processed/`.
- Record the source URL, licence and access date here **before** training on a dataset.
- Never commit personal or identifiable data.
