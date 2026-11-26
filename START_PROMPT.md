# First prompt to paste into Claude Code (Phase 0)

```
Read SPEC.md fully. It is the source of truth for this project.

We are doing Phase 0 only. Do not start later phases.

1. Create CLAUDE.md with:
   - a 5-line project summary and a pointer to SPEC.md
   - the folder layout from SPEC.md section 3
   - commands to run web, api, tests and docker compose
   - rules: never read or print .env; never hard-code secrets, read them
     from env via api/app/core/config.py (pydantic-settings); never
     paraphrase validated questionnaire items; the safety check always
     runs before scoring and ML; the validated score always takes priority
     over the ML estimate; write tests with every feature; keep commits
     small with conventional commit messages; never add Co-Authored-By or
     "Generated with" lines to commits or PRs.
2. Scaffold the monorepo exactly as in SPEC.md section 3:
   - web/: Next.js 15 App Router + TypeScript + Tailwind + shadcn/ui,
     with the colours and fonts from SPEC.md section 9 set up as theme
     tokens, and a placeholder landing page in that style.
   - api/: FastAPI + SQLAlchemy 2 + Alembic + pydantic-settings, with
     GET /api/v1/health and a config module that reads every variable
     in .env.example.
   - ml/: folder skeleton with a README and requirements.txt
     (scikit-learn, xgboost, shap, pandas, joblib).
3. docker-compose.yml with services web (3000), api (8000) and db
   (postgres:16), all reading from .env. Keep memory use low: no extra
   services.
4. .gitignore covering .env, node_modules, __pycache__, .venv,
   ml/data/raw, ml/models/*.joblib, .next.
5. GitHub Actions workflow: lint + tests for web and api on push.
6. Run everything to check that it works: docker compose up, then curl
   the health endpoint and load the web page. Fix any errors.

When finished, show me the file tree, what you verified, and the exact
commands I should run. Don't commit; I'll review and commit myself.
```

## Prompts for later phases (one per session)

Start each new session with:

```
Read CLAUDE.md and SPEC.md. We are doing Phase <N> from SPEC.md
section 12. Plan first (list files you'll create/change), wait for my
OK, then build it with tests, run the tests, and summarise.
Don't commit.
```
