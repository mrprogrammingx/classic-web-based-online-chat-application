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
except Exception:
    # Log but do not fail the container startup; the app will also attempt
    # to initialize on startup and can surface the error. Failing here may
    # be too aggressive for some deployment flows.
    import traceback
    print('[entrypoint] DB init encountered exception:')
    traceback.print_exc()
PY

# If the user requested multiple workers, enable SQLite WAL mode so the
# database supports concurrent readers/writers across processes. We only
# attempt this when UVICORN_WORKERS is set to an integer > 1.
if [ -n "${UVICORN_WORKERS:-}" ] && [ "${UVICORN_WORKERS}" -gt 1 ] 2>/dev/null; then
  echo "[entrypoint] UVICORN_WORKERS=${UVICORN_WORKERS} -> ensuring SQLite WAL journal mode"
  # Use AUTH_DB_PATH env if present, otherwise default to where the compose file mounts the DB.
  DB_PATH="${AUTH_DB_PATH:-/data/auth.db}"
  # Ensure parent directory exists (in case /data is an empty volume)
  mkdir -p "$(dirname "$DB_PATH")"
  python - <<'PY'
import os, sqlite3
db = os.getenv('AUTH_DB_PATH', '/data/auth.db')
try:
    conn = sqlite3.connect(db)
    cur = conn.cursor()
    cur.execute('PRAGMA journal_mode=WAL;')
    res = cur.fetchone()
    print('[entrypoint] PRAGMA journal_mode result:', res)
    conn.commit()
except Exception:
    import traceback
    print('[entrypoint] Failed to set WAL mode on DB:')
    traceback.print_exc()
finally:
    try:
        conn.close()
    except Exception:
        pass
PY
fi

echo "[entrypoint] Starting server: $@"

# Build command array to allow appending --workers safely
cmd=("$@")

# If UVICORN_WORKERS requests multiple workers, and the command does not
# already include --reload or --workers, append --workers <N> so Docker
# env can control concurrency from docker-compose. This mirrors the
# behavior documented in docker-compose.yml.
if [ -n "${UVICORN_WORKERS:-}" ] && [ "${UVICORN_WORKERS}" -gt 1 ] 2>/dev/null; then
    reload_present=0
    workers_present=0
    for a in "${cmd[@]}"; do
        if [ "$a" = "--reload" ]; then
            reload_present=1
        fi
        if [ "$a" = "--workers" ]; then
            workers_present=1
        fi
    done
    if [ "$reload_present" -eq 0 ] && [ "$workers_present" -eq 0 ]; then
        cmd+=("--workers" "${UVICORN_WORKERS}")
    fi
fi

exec "${cmd[@]}"
