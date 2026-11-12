#!/bin/sh
set -eu

if [ "${MP_SKIP_MIGRATIONS:-false}" != "true" ]; then
  echo "[entrypoint] Running database migrations..."
  alembic upgrade head
fi

echo "[entrypoint] Starting API server on port ${MP_API_PORT:-8000}..."
exec uvicorn app.main:app --host 0.0.0.0 --port "${MP_API_PORT:-8000}" --workers 1
