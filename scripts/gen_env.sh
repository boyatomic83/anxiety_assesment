#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
if [ -f .env ]; then echo ".env already exists - not overwriting." >&2; exit 1; fi
rand() { python3 -c "import secrets; print(secrets.token_urlsafe($1))"; }
PG_PASS=$(rand 24); JWT=$(rand 64); ADMIN_PASS=$(rand 16)
FERNET=$(python3 -c "import base64,os; print(base64.urlsafe_b64encode(os.urandom(32)).decode())")
sed -e "s|^POSTGRES_PASSWORD=.*|POSTGRES_PASSWORD=${PG_PASS}|" \
    -e "s|^DATABASE_URL=.*|DATABASE_URL=postgresql+psycopg://calma:${PG_PASS}@db:5432/calma|" \
    -e "s|^JWT_SECRET_KEY=.*|JWT_SECRET_KEY=${JWT}|" \
    -e "s|^ENCRYPTION_KEY=.*|ENCRYPTION_KEY=${FERNET}|" \
    -e "s|^ADMIN_PASSWORD=.*|ADMIN_PASSWORD=${ADMIN_PASS}|" \
    .env.example > .env
chmod 600 .env
echo "Created .env. Admin login: admin@example.com / ${ADMIN_PASS}"
