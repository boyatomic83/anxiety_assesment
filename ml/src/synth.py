"""Synthetic data generator (SPEC.md section 6.2, Phase A).

THE DATA IS SIMULATED. Metrics computed on it say nothing about clinical validity; they only
prove the pipeline works end to end. See reports/MODEL_CARD.md.

A latent anxiety trait drives GAD-7 and OASIS items; a correlated latent depression trait
drives PHQ-9. The label is a composite severity derived from the latent traits, symptom
duration and impairment, so it is related to, but not identical with, any single score.
"""

import numpy as np
import pandas as pd

from src.features import ITEM_FEATURES, build_features, FEATURES

AGE_BANDS = ["18-24", "25-34", "35-44", "45-54", "55-64", "65+"]
GENDERS = ["female", "male", "non_binary", "prefer_not"]
DURATIONS = ["<2w", "2w-1m", "1-6m", "6m+"]


def _ordinal(latent: np.ndarray, loading: float, offset: float, top: int, rng) -> np.ndarray:
    raw = offset + loading * latent + rng.normal(0, 0.55, latent.shape)
    return np.clip(np.rint(raw), 0, top).astype(int)


def generate(n: int = 6000, seed: int = 7) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    anx = rng.normal(0, 1, n)
    dep = 0.6 * anx + 0.8 * rng.normal(0, 1, n)

    rows: dict[str, np.ndarray] = {}
    for i in range(1, 8):
        rows[f"gad7_{i}"] = _ordinal(anx, rng.uniform(0.8, 1.1), 1.0 + rng.uniform(-0.3, 0.2), 3, rng)
    for i in range(1, 10):
        off = 0.9 + rng.uniform(-0.3, 0.2) - (0.9 if i == 9 else 0)  # item 9 is rarer
        rows[f"phq9_{i}"] = _ordinal(dep, rng.uniform(0.7, 1.0), off, 3, rng)
    for i in range(1, 6):
        rows[f"oasis_{i}"] = _ordinal(anx, rng.uniform(1.0, 1.3), 1.3 + rng.uniform(-0.3, 0.2), 4, rng)

    age = rng.choice(len(AGE_BANDS), n, p=[0.22, 0.28, 0.2, 0.14, 0.1, 0.06])
    gender = rng.choice(len(GENDERS), n, p=[0.48, 0.46, 0.03, 0.03])
    sleep = np.clip(7.4 - 0.6 * anx - 0.3 * dep + rng.normal(0, 1.0, n), 3, 11).round(1)
    duration = np.clip(np.rint(1.2 + 0.7 * anx + rng.normal(0, 0.8, n)), 0, 3).astype(int)
    stress = rng.random(n) < 1 / (1 + np.exp(-(0.9 * anx - 0.6)))
    caffeine = rng.poisson(np.clip(2 + 0.4 * anx, 0.2, None))
    impairment = 0.5 * anx + 0.3 * dep + rng.normal(0, 0.5, n)

    # Composite ground truth from latents, then cut at fixed quantiles (40/30/20/10 %).
    composite = 0.65 * anx + 0.2 * dep + 0.15 * (duration - 1.5) + 0.25 * impairment
    composite += rng.normal(0, 0.25, n)
    cuts = np.quantile(composite, [0.4, 0.7, 0.9])
    label = np.digitize(composite, cuts)

    # Item timings, plus ~3% careless responders (fast and/or straight-lining).
    secs = rng.lognormal(np.log(4.0), 0.45, (n, len(ITEM_FEATURES)))
    careless = rng.random(n) < 0.03
    secs[careless] = rng.uniform(0.3, 1.2, (careless.sum(), len(ITEM_FEATURES)))
    for name in ITEM_FEATURES:
        top = 4 if name.startswith("oasis") else 3
        rows[name] = np.where(careless, rng.integers(0, top + 1), rows[name])
    straight = careless & (rng.random(n) < 0.5)
    for name in ITEM_FEATURES:
        rows[name] = np.where(straight, 1, rows[name])

    records = []
    for k in range(n):
        answers = {
            q: {f: int(rows[f][k]) for f in ITEM_FEATURES if f.startswith(q + "_")}
            for q in ("gad7", "phq9", "oasis")
        }
        ctx = {
            "age_band": AGE_BANDS[age[k]],
            "sleep_hours": float(sleep[k]) if rng.random() > 0.1 else None,  # 10% skip
            "symptom_duration": DURATIONS[duration[k]],
            "stressful_event": bool(stress[k]),
            "caffeine_cups": int(caffeine[k]) if rng.random() > 0.15 else None,
        }
        timings = dict(zip(ITEM_FEATURES, secs[k].round(2), strict=True))
        x = build_features(answers, ctx, timings)
        records.append([*x, GENDERS[gender[k]], AGE_BANDS[age[k]], int(label[k])])
    return pd.DataFrame(records, columns=[*FEATURES, "gender", "age_group", "label"])


if __name__ == "__main__":
    import argparse
    from pathlib import Path

    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=6000)
    ap.add_argument("--out", default=str(Path(__file__).resolve().parents[1] / "data/processed/synth.csv"))
    a = ap.parse_args()
    df = generate(a.n)
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(a.out, index=False)
    print(f"wrote {len(df)} rows to {a.out}; label counts {df.label.value_counts().sort_index().tolist()}")
