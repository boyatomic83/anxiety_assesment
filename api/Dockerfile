# syntax=docker/dockerfile:1
FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /app
COPY requirements.txt ./
# Build-time workaround: some networks (incl. GitHub Codespaces) drop the large post-quantum
# TLS ClientHello that OpenSSL 3.5 sends, so pip hangs on PyPI. Limit key-exchange groups
# for this step only; the runtime image keeps the default OpenSSL config.
RUN printf 'openssl_conf=i\n[i]\nssl_conf=s\n[s]\nsystem_default=d\n[d]\nGroups=X25519:prime256v1\n' > /tmp/pip-openssl.cnf \
 && OPENSSL_CONF=/tmp/pip-openssl.cnf pip install -r requirements.txt \
 && rm /tmp/pip-openssl.cnf
COPY . .
RUN useradd --create-home --uid 1001 calma
USER calma
EXPOSE 8000
# Apply migrations, then serve. One worker keeps memory low in Codespaces.
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 1 --proxy-headers --forwarded-allow-ips=*"]
