# SPEC — Calma: Anxiety Screening & Severity Assessment Platform

> Status: v1 spec · Owner: <your-name> · Last updated: 2026-11-26
> Calma is a **screening** tool, not a diagnostic tool. Every screen that shows a result must say so.

---

## 1. Goal

A web platform where a user completes validated clinical anxiety questionnaires through a calm, accessible interface. The backend scores them with the **official validated rules**, an ML model adds a **composite risk estimate with explanations**, and the user (and optionally a clinician) gets a clear report and a history of results over time.

### Non-goals (v1)
- No diagnosis, no treatment recommendations beyond general next steps.
- No chat or therapy bot.
- No licensed instruments (BAI, STAI) unless a licence is obtained.

---

## 2. Users & roles

| Role | Can do |
|---|---|
| **Guest** | Take an assessment anonymously, see the result, download a PDF. Nothing is stored after 24h unless they sign up. |
| **User** | Everything a guest can, plus saved history, trend charts, re-test reminders, delete-my-data. |
| **Clinician** | See users who shared results with them (via a share code), flagged cases, trends, exports. |
| **Admin** | Manage questionnaire definitions, model versions, view audit logs. |

---

## 3. Repository layout

```
calma/
├── SPEC.md                 ← this file (source of truth)
├── CLAUDE.md               ← rules for Claude Code
├── .env.example            ← every env var, no real values
├── docker-compose.yml      ← web + api + db
├── .devcontainer/          ← GitHub Codespaces config
├── web/                    ← Next.js 15 (App Router) + TS + Tailwind + shadcn/ui
│   ├── app/
│   │   ├── (public)/       landing, about, consent
│   │   ├── assess/         assessment flow
│   │   ├── results/[id]/   result page
│   │   ├── dashboard/      user history
│   │   └── clinician/      clinician dashboard
│   ├── components/
│   └── lib/api.ts          typed API client
├── api/                    ← FastAPI + SQLAlchemy 2 + Alembic + Pydantic v2
│   ├── app/
│   │   ├── main.py
│   │   ├── core/           config, security, encryption
│   │   ├── models/         SQLAlchemy models
│   │   ├── schemas/        Pydantic schemas
│   │   ├── routers/        auth, questionnaires, sessions, results, clinician, admin
│   │   ├── services/
│   │   │   ├── scoring.py  deterministic validated scoring
│   │   │   ├── safety.py   crisis detection (runs FIRST)
│   │   │   ├── ml.py       model loading + predict + SHAP
│   │   │   └── report.py   PDF generation
│   │   └── questionnaires/ JSON definitions (gad7.json, phq9.json, ...)
│   ├── alembic/
│   └── tests/
└── ml/
    ├── data/               raw/ processed/ (gitignored except README)
    ├── notebooks/          EDA
    ├── src/                features.py, train.py, evaluate.py
    ├── models/             saved model artifacts (gitignored; small ones OK)
    └── reports/            metrics, calibration plots, model card
```

---

## 4. Questionnaires (data-driven)

Every questionnaire is a JSON file. Adding one requires **no code changes**.

### v1 set
| ID | Name | Items | Range | Licence |
|---|---|---|---|---|
| `gad2` | GAD-2 | 2 | 0–6 | Free |
| `gad7` | GAD-7 | 7 | 0–21 | Free |
| `phq9` | PHQ-9 | 9 | 0–27 | Free |
| `oasis` | OASIS | 5 | 0–20 | Free |
| `dass21` | DASS-21 | 21 | subscales ×2 | Public domain |

v2 candidates: PCL-5 (PTSD), SPIN (social anxiety), PDSS-SR (panic). Check each licence before adding.

### JSON schema (example: `gad7.json`)
```json
{
  "id": "gad7",
  "name": "GAD-7",
  "version": "1.0",
  "timeframe": "Over the last 2 weeks, how often have you been bothered by the following problems?",
  "options": [
    {"value": 0, "label": "Not at all"},
    {"value": 1, "label": "Several days"},
    {"value": 2, "label": "More than half the days"},
    {"value": 3, "label": "Nearly every day"}
  ],
  "items": [
    {"id": "gad7_1", "text": "Feeling nervous, anxious, or on edge"}
  ],
  "scoring": {"method": "sum"},
  "bands": [
    {"min": 0,  "max": 4,  "label": "Minimal",  "level": 0},
    {"min": 5,  "max": 9,  "label": "Mild",     "level": 1},
    {"min": 10, "max": 14, "label": "Moderate", "level": 2},
    {"min": 15, "max": 21, "label": "Severe",   "level": 3}
  ],
  "safety_items": [],
  "source": "Spitzer et al., 2006",
  "i18n": {"hi": {"...": "..."}}
}
```
Item texts must be copied **exactly** from the official instrument. Do not paraphrase validated items.

Scoring methods to support: `sum`, `sum_x2` (DASS-21 subscales), `subscales` (named item groups).

---

## 5. User flow

```
Landing ──► Consent + disclaimer ──► Basic context (age band, optional gender, language)
   │
   ▼
GAD-2 screener (2 questions)
   │
   ├── score < 3 ──► short result: "Low likelihood of anxiety disorder" + optional full check
   │
   └── score ≥ 3 ──► GAD-7 (remaining 5 items) ──► PHQ-9 ──► OASIS
                                                     │
                       ┌─────────────────────────────┘
                       ▼
             Optional lifestyle context (sleep hours, duration of symptoms,
             caffeine, recent stressful event – yes/no)
                       │
                       ▼
             Optional free text: "Anything else you'd like to share?"
                       │
                       ▼
  ┌──────────── SAFETY CHECK (every submit, before anything else) ───────────┐
  │ PHQ-9 item 9 > 0  OR  crisis keywords in free text  →  Crisis screen     │
  │ (helplines shown immediately, result still available after)             │
  └─────────────────────────────────────────────────────────────────────────┘
                       │
                       ▼
           Scoring engine (validated) ──► ML service (composite + SHAP)
                       │
                       ▼
                  Results page ──► PDF report / Save to history / Share with clinician
```

### Crisis screen
- Shown full screen, calm and non-alarming: "You don't have to go through this alone."
- Helplines by locale. India: **Tele-MANAS 14416** (also 1-800-891-4416), emergency **112**. Keep helplines in `api/app/core/helplines.json`, not hard-coded in components.
- Sets `flagged=true` on the session. Clinicians see flagged sessions first.
- Never blocks the user from continuing to see their results.

---

## 6. Scoring & ML

### 6.1 Deterministic scoring (primary result, always shown)
- `services/scoring.py` takes `(questionnaire_json, answers)` and returns `{total, subscales, band, level}`.
- 100% unit test coverage against known score→band examples for every questionnaire.

### 6.2 ML composite (secondary result, labelled "AI-assisted estimate")
**Inputs (features):** item-level answers from GAD-7, PHQ-9 and OASIS, age band, sleep hours, symptom duration, stressful-event flag, response time per item.

**Outputs:**
- `composite_severity`: 0–3 class (minimal/mild/moderate/severe) plus class probabilities
- `confidence`: max probability
- `top_factors`: top 5 SHAP contributions as `{feature, label, impact}`
- `response_quality`: flag for careless responding (e.g. all identical answers, very fast completion, contradictory items)
- `model_version`

**Models:** logistic regression (baseline) → XGBoost/LightGBM. Pick by macro-F1 and calibration.

**Data plan:**
1. Phase A: synthetic data generator (`ml/src/synth.py`) to build and test the pipeline. **Document in the model card that metrics on synthetic data mean nothing clinically.**
2. Phase B: a real, openly licensed dataset containing GAD-7 and/or DASS items (Kaggle/OSF/published supplementary data). Record its source and licence in `ml/data/README.md`.

**Evaluation (in `ml/reports/`):** stratified 5-fold CV, macro-F1, ROC-AUC (one-vs-rest), confusion matrix, calibration plot, and a subgroup breakdown by age band and gender.

**Model card** (`ml/reports/MODEL_CARD.md`): data, intended use, limits, metrics, fairness, version.

**Rule:** when the ML band disagrees with the validated band, the UI shows both and the validated one takes priority.

### 6.3 Optional NLP (v2)
Free-text → sentiment/anxiety-themes classifier (small transformer, run on CPU). Used only as an extra signal and for crisis keyword detection backup.

---

## 7. API (FastAPI, prefix `/api/v1`)

| Method | Path | Purpose |
|---|---|---|
| POST | `/auth/register` · `/auth/login` · `/auth/refresh` | JWT auth |
| GET | `/questionnaires` | List available questionnaires |
| GET | `/questionnaires/{id}?lang=en` | Full definition |
| POST | `/sessions` | Start an assessment session (guest or user) |
| POST | `/sessions/{id}/answers` | Save answers for one questionnaire (autosave) |
| POST | `/sessions/{id}/submit` | Safety → scoring → ML; returns result |
| GET | `/results/{id}` | Result detail |
| GET | `/results/{id}/pdf` | PDF report |
| GET | `/me/history` | User's past results |
| DELETE | `/me` | Delete account + all data |
| POST | `/results/{id}/share` | Create share code for a clinician |
| GET | `/clinician/patients` · `/clinician/flagged` | Clinician views |
| GET | `/admin/audit` · `/admin/models` | Admin |
| GET | `/health` | Health check |

All responses use Pydantic schemas. OpenAPI docs at `/docs` (disabled in production).

---

## 8. Data model (PostgreSQL)

- `users` (id, email, password_hash, role, locale, created_at)
- `sessions` (id, user_id NULL for guests, status, started_at, submitted_at, flagged, context_json_encrypted)
- `responses` (id, session_id, questionnaire_id, questionnaire_version, answers_encrypted, item_timings_json)
- `results` (id, session_id, scores_json, ml_json, model_version, created_at)
- `shares` (id, result_id, code, clinician_id, expires_at)
- `audit_logs` (id, actor_id, action, target, ip_hash, created_at)

Answers and free text are encrypted at rest with Fernet (`ENCRYPTION_KEY`). Guest sessions are deleted after 24h by a scheduled job.

---

## 9. Frontend design system

**Feel:** calm, clinical, trustworthy, like a modern hospital app, not a game.

- **Colours:** background `#F7F8F6`, surface `#FFFFFF`, text `#1F2A2E`, primary sage `#5B8A72`, secondary slate `#5A7184`. Severity bands: minimal `#7FB59A`, mild `#C9B458`, moderate `#D9905B`, severe `#B5615A` (muted, never neon red).
- **Type:** headings in *Fraunces* or *Source Serif*, body in *Inter*. Base 17px, line-height 1.6.
- **Layout:** max width 640px for the assessment, lots of white space, 16px radius cards, soft shadows.
- **Assessment UX:** one question per screen, large tappable options (≥48px), keyboard shortcuts 1–4, a progress bar ("Question 4 of 7"), back button, autosave, gentle Framer Motion transitions (≤250ms, respects `prefers-reduced-motion`).
- **Results page:** semicircle severity gauge, plain-language summary, "what drove this" SHAP bar chart, next steps, disclaimer, PDF download.
- **Dashboard:** line chart of GAD-7 / PHQ-9 over time with band backgrounds.
- **Accessibility:** WCAG 2.2 AA, full keyboard navigation, ARIA labels, contrast checked.
- **i18n:** English + Hindi in v1 (next-intl). Use only official validated translations of questionnaires.
- Dark mode: optional, v2.

---

## 10. Security & privacy

- Passwords: argon2. JWT access token 15 min, refresh token 7 days (httpOnly cookie).
- Encryption at rest for answers and free text; TLS in transit.
- CORS limited to `CORS_ORIGINS`. Rate limit auth and submit endpoints.
- No secrets in code. Everything goes through `.env` (see `.env.example`). `.env` is gitignored.
- Explicit consent screen with version stored per session.
- User can export and delete their data (India DPDP Act 2023; GDPR-style rights).
- Audit log for clinician/admin access.
- No analytics trackers on assessment pages.

---

## 11. Testing

- `api`: pytest. Scoring for every questionnaire, safety rules, API integration tests against a test DB.
- `web`: Vitest + React Testing Library for components; Playwright for one end-to-end assessment run.
- `ml`: tests for the feature pipeline and that the saved model loads and predicts the right shape.
- CI: GitHub Actions running lint + tests on every push.

---

## 12. Build phases (one phase per Claude Code session)

| Phase | Deliverable | Done when |
|---|---|---|
| 0 | Repo skeleton, docker-compose, devcontainer, CLAUDE.md, CI | `docker compose up` shows web on :3000 and api `/health` on :8000 |
| 1 | Questionnaire JSONs + scoring engine + tests | All scoring tests pass |
| 2 | DB models, Alembic, sessions/answers/submit API, safety service | Can submit via `/docs` and get scores |
| 3 | Frontend: landing, consent, assessment flow, crisis screen | Full flow works in browser |
| 4 | Results page + PDF report | Result renders with gauge + PDF downloads |
| 5 | ML: synth data, training, evaluation, model card, `/predict` integration with SHAP | Results show the AI estimate + top factors |
| 6 | Auth, history dashboard, delete-my-data | Logged-in user sees trend chart |
| 7 | Clinician dashboard, share codes, audit log | Clinician sees shared + flagged results |
| 8 | i18n (Hindi), accessibility pass, hardening, deploy | Lighthouse a11y ≥ 95, deployed |

---

## 13. Deployment (free/cheap options)

- **Web:** Vercel
- **API:** Render / Railway / Fly.io (Docker)
- **DB:** Neon or Supabase Postgres (free tier)
- Model artifact shipped inside the API image (it is small: sklearn/XGBoost).
