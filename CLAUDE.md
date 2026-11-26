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

# ML (from ml/)
pip install -r requirements.txt
```

Theme tokens live in `web/app/globals.css` (SPEC.md section 9). Use `bg-sage`, `text-slate-brand`,
`bg-band-{minimal,mild,moderate,severe}`, `font-serif` (Fraunces) and `font-sans` (Inter).
`--primary` is a deeper sage (`#4A7561`) so that white button text meets WCAG AA. Spec sage
`#5B8A72` is still available as `sage`.

## Rules

- **Never read, print, cat or grep `.env`.** Secrets are never echoed in logs or output.
- **Never hard-code secrets.** Read every setting from the environment through
  `api/app/core/config.py` (pydantic-settings). When you add an env var, add it to `.env.example`
  (no real values) and to `Settings`.
- **Never paraphrase validated questionnaire items.** Item text, options and timeframes are copied
  exactly from the official instrument, and only official validated translations are used.
- **The safety check always runs first**, before scoring and before ML, on every submit.
- **The validated score always takes priority** over the ML estimate. When the two disagree, show
  both and mark the validated one as primary. Label the ML output "AI-assisted estimate".
- Every result screen states that Calma is a screening tool, not a diagnosis.
- Write tests with every feature. Keep CI (lint + tests) green.
- Small commits with conventional commit messages (`feat:`, `fix:`, `chore:`, `test:`, `docs:`...).
- Never add `Co-Authored-By` or "Generated with" lines to commits or PRs.
- **Never commit.** The user reviews and commits.
- Do one phase per session (SPEC.md section 12). Don't start later phases early.
