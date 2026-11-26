# Deploying Calma (SPEC.md section 13)

Nothing here runs automatically. Each step publishes to an external service, so do it yourself.

## Option A: everything on Render (one blueprint)
`render.yaml` creates **calma-db** (Postgres 16), **calma-api** and **calma-web**.
1. Commit and push to GitHub.
2. Render > **New > Blueprint** > connect GitHub > pick this repo > **Apply**.
3. Fill in the prompted values:
   - `ENCRYPTION_KEY`: generate one locally and keep a copy (losing it makes stored answers unreadable):
     `python3 -c "import base64,os;print(base64.urlsafe_b64encode(os.urandom(32)).decode())"`
   - `CORS_ORIGINS` and `WEB_URL`: `https://calma-web.onrender.com` (or whatever URL Render gives calma-web)
   - `NEXT_PUBLIC_API_URL`: `https://calma-api.onrender.com` (calma-api's URL; baked in at build time)
   - `ADMIN_EMAIL` / `ADMIN_PASSWORD`: the bootstrap admin account
4. If Render gave the services different URLs, update those values and redeploy **calma-web**
   (the API URL is baked into its build).
5. Check `https://<calma-api>.onrender.com/api/v1/health` returns `"database":"ok"`.

Free plan notes: services sleep after ~15 min idle (first request takes ~1 min), and free
Postgres expires after 30 days.

## Option B: Vercel (web) + Render (API) + Neon/Supabase (DB)
- Database: create Postgres 16 and copy the URL (`postgres://...` is fine, the API converts it;
  add `?sslmode=require`).
- API: create a Render Docker web service with root directory `api`, using the same env vars
  as above plus `DATABASE_URL`.
- Web: Vercel > New Project > root directory `web`, env `NEXT_PUBLIC_API_URL=<API URL>`.

## Cookies across two domains
The refresh token is an httpOnly cookie set by the API. With the web app on `*.vercel.app` and
the API on `*.onrender.com`, it's a cross-site cookie (`SameSite=None; Secure` in production),
which some browsers block. For reliable sign-in, put both on one domain you own, e.g.
`app.example.com` (Vercel) and `api.example.com` (Render), and update `CORS_ORIGINS`.

## Before real users
- Retrain the model on a real, openly licensed dataset (SPEC 6.2 Phase B); the bundled model is
  trained on synthetic data and the UI says so.
- Review the Hindi UI copy with a native speaker. Add official Hindi questionnaire wording only
  from a validated source (see `api/app/questionnaires/items/SOURCES.json`).
- The in-memory rate limiter is per process. Keep one API instance, or move it to Redis.
