#!/usr/bin/env bash
set -euo pipefail

# docker-entrypoint.sh
# Ensure DB schema is initialized once before starting the app server.
# This avoids race conditions when running multiple uvicorn workers or
# when the app startup would otherwise try to create the schema concurrently.

echo "[entrypoint] Initializing database schema (if needed)..."
python - <<'PY'
import asyncio
import db

try:
    asyncio.run(db.init_db())
    print('[entrypoint] DB init completed')
except Exception as e:
    # Log but do not fail the container startup; the app will also attempt
    # to initialize on startup and can surface the error. Failing here may
    # be too aggressive for some deployment flows.
    import traceback
    print('[entrypoint] DB init encountered exception:')
    traceback.print_exc()
PY

echo "[entrypoint] Starting server: $@"
exec "$@"
