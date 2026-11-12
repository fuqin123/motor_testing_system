#!/bin/sh
set -eu

if [ "${MP_SKIP_MIGRATIONS:-false}" != "true" ]; then
  echo "[entrypoint] Running database migrations..."
  alembic upgrade head
fi

echo "[entrypoint] Starting API server..."
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}" --workers 1
