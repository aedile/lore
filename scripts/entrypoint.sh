#!/usr/bin/env bash
# scripts/entrypoint.sh — Container startup script for lore-eligibility.
#
# Sequence:
#   1. Wait for PostgreSQL to accept connections (readiness probe).
#   2. Run pending Alembic migrations.
#   3. Exec the CMD passed by the Dockerfile (defaults to uvicorn).
#
# DATABASE_URL must be set in the environment (see .env.example).

set -euo pipefail

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

log() {
    printf '[entrypoint] %s\n' "$*"
}

# ---------------------------------------------------------------------------
# Wait for PostgreSQL
# ---------------------------------------------------------------------------

if [[ -z "${DATABASE_URL:-}" ]]; then
    log "ERROR: DATABASE_URL is not set."
    exit 1
fi

# Extract host/port from the DSN. Tolerate both async and sync schemes.
PG_HOST=$(python -c "from urllib.parse import urlparse; u=urlparse('${DATABASE_URL}'); print(u.hostname or 'localhost')")
PG_PORT=$(python -c "from urllib.parse import urlparse; u=urlparse('${DATABASE_URL}'); print(u.port or 5432)")

log "Waiting for PostgreSQL at ${PG_HOST}:${PG_PORT}..."

for attempt in $(seq 1 30); do
    if python - <<PY 2>/dev/null
import socket
s = socket.socket()
s.settimeout(2)
try:
    s.connect(("${PG_HOST}", ${PG_PORT}))
    s.close()
except Exception:
    raise SystemExit(1)
PY
    then
        log "PostgreSQL is reachable (attempt ${attempt})."
        break
    fi
    if [[ "${attempt}" -eq 30 ]]; then
        log "ERROR: PostgreSQL not reachable after 30 attempts."
        exit 1
    fi
    sleep 2
done

# ---------------------------------------------------------------------------
# Run Alembic migrations (idempotent)
# ---------------------------------------------------------------------------

if [[ -f /app/alembic.ini ]]; then
    log "Running Alembic migrations..."
    alembic -c /app/alembic.ini upgrade head
    log "Migrations complete."
else
    log "alembic.ini not found — skipping migrations."
fi

# ---------------------------------------------------------------------------
# Exec the CMD
# ---------------------------------------------------------------------------

log "Starting application: $*"
exec "$@"
