# CLAUDE.md

**Calma** is an anxiety **screening** platform (not a diagnostic tool). Users complete validated
questionnaires (GAD-2/7, PHQ-9, OASIS, DASS-21) in a calm, accessible Next.js UI. A FastAPI
backend runs a safety check, scores answers with the official validated rules, and adds a
secondary ML "AI-assisted estimate" with SHAP explanations. Results, history and clinician
sharing are stored in Postgres, with answers encrypted at rest.

**SPEC.md is the source of truth.** Read it before every phase (build phases: SPEC.md section 12).

## Layout (SPEC.md section 3)

```
.
├── SPEC.md  CLAUDE.md  .env.example  docker-compose.yml
├── .devcontainer/          Codespaces config
├── .github/workflows/      CI (lint + tests)
├── web/                    Next.js 15 (App Router) + TS + Tailwind v4 + shadcn/ui
│   ├── app/
│   │   ├── (public)/       landing, about, consent
│   │   ├── assess/         assessment flow
│   │   ├── results/[id]/   result page
│   │   ├── dashboard/      user history
│   │   └── clinician/      clinician dashboard
│   ├── components/         (ui/ = shadcn)
│   ├── lib/api.ts          typed API client
│   └── tests/              Vitest + RTL
├── api/                    FastAPI + SQLAlchemy 2 + Alembic + Pydantic v2
│   ├── app/
│   │   ├── main.py
│   │   ├── core/           config (pydantic-settings), security, encryption
│   │   ├── models/         SQLAlchemy models
│   │   ├── schemas/        Pydantic schemas
│   │   ├── routers/        auth, questionnaires, sessions, results, clinician, admin
│   │   ├── services/       scoring.py, safety.py, ml.py, report.py
│   │   └── questionnaires/ JSON definitions
│   ├── alembic/
│   └── tests/              pytest
└── ml/                     data/ notebooks/ src/ models/ reports/
```

## Commands

```bash
# First time only: create .env from .env.example with random secrets
./scripts/gen_env.sh

# Whole stack (web :3000, api :8000, db internal)
docker compose up -d --build
docker compose logs -f api
docker compose down            # add -v to also wipe the Postgres volume

# Web (from web/)
npm ci
npm run dev                    # http://localhost:3000
npm run lint && npm run typecheck && npm test

# API (from api/)
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements-dev.txt
uvicorn app.main:app --reload --port 8000   # needs a reachable DATABASE_URL
ruff check . && ruff format --check . && pytest
alembic revision --autogenerate -m "..." && alembic upgrade head

# Questionnaire wording (re-download official forms, extract to api/app/questionnaires/items/)
api/.venv/bin/python scripts/fetch_questionnaires.py           # prints line counts only
api/.venv/bin/python scripts/fetch_questionnaires.py --check   # verify counts, no download

# ML (from ml/): retrain + export to api/app/ml_models/ + regenerate ml/reports/
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python -m src.train
.venv/bin/python -m pytest -q tests

# End-to-end + accessibility (needs the stack running: docker compose up -d --build)
cd web && npx playwright install --with-deps chromium && npm run test:e2e
```

**Lock file:** this Codespace's npm may differ from Node 22's npm used in Docker/CI. After any
`npm install`, resync with:
`docker run --rm -u "$(id -u):$(id -g)" -e npm_config_cache=/tmp/npmcache -v "$PWD/web:/app" -w /app node:22-alpine npm install --package-lock-only`

Theme tokens live in `web/app/globals.css` (SPEC.md section 9). Use `bg-sage`, `text-slate-brand`,
`bg-band-{minimal,mild,moderate,severe}`, `font-serif` (Fraunces) and `font-sans` (Inter).
`--primary` is a deeper sage (`#4A7561`) and `--muted-foreground` a deeper slate (`#50677A`) so
text meets WCAG AA. Spec sage `#5B8A72` / slate `#5A7184` are still available as `sage` /
`slate-brand` for decoration. UI copy lives in `web/messages/{en,hi}.json` (same keys, enforced
by a test); questionnaire wording never does.

## Architecture notes
- Submit pipeline: `api/app/services/assessment.py` runs safety -> validated scoring -> ML.
- Guest sessions are authorised by an `X-Session-Token` header (only its keyed hash is stored)
  and purged after 24h by `services/jobs.py`; signed-in users use a 15-min bearer token plus a
  7-day httpOnly refresh cookie.
- ML artifacts are JSON (no pickle) in `api/app/ml_models/`; the feature pipeline lives in
  `api/app/services/features.py` and `ml/src` imports it, so training and serving can't drift.
- Hindi questionnaire wording: the official Pfizer Hindi PDFs lose glyphs on extraction, so
  items are shown in English with a notice. Add translations only as files in `items/` via
  `"i18n": {"hi": {"text_file", "timeframe_file", "options_file"}}`; never type them.

## Rules

- **Never read, print, cat or grep `.env`.** Secrets are never echoed in logs or output.
- **Never hard-code secrets.** Read every setting from the environment through
  `api/app/core/config.py` (pydantic-settings). When you add an env var, add it to `.env.example`
  (no real values) and to `Settings`.
- **Never paraphrase validated questionnaire items.** Item text, options and timeframes are copied
  exactly from the official instrument, and only official validated translations are used.
- **Never type questionnaire wording yourself** (in replies, JSON or tests). JSON definitions in
  `api/app/questionnaires/` hold structure only and reference `items/*.txt` via `text_file`,
  `options_file`, `timeframe_file`; those files come from `scripts/fetch_questionnaires.py`.
  Never print their contents; check line counts instead. Tests use item ids and values only.
- **The safety check always runs first**, before scoring and before ML, on every submit.
- **The validated score always takes priority** over the ML estimate. When the two disagree, show
  both and mark the validated one as primary. Label the ML output "AI-assisted estimate".
- Every result screen states that Calma is a screening tool, not a diagnosis.
- Write tests with every feature. Keep CI (lint + tests) green.
- Small commits with conventional commit messages (`feat:`, `fix:`, `chore:`, `test:`, `docs:`...).
- Never add `Co-Authored-By` or "Generated with" lines to commits or PRs.
- **Never commit.** The user reviews and commits.
- Do one phase per session (SPEC.md section 12). Don't start later phases early.
