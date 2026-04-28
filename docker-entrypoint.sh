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

# If WAL was reported as enabled, check that the underlying WAL/-SHM files
# were created. If they are missing or PRAGMA didn't return 'wal', provide
# an actionable warning. Many problems are caused by bind-mounting the DB
# onto network filesystems (NFS/SMB) which don't support SQLite shared-memory
# files required for WAL mode. Prefer using Docker named volumes (the
# `chat_data` named volume in docker-compose.yml) or switch to a client
# DB like Postgres for production workloads.
if [ -n "${UVICORN_WORKERS:-}" ] && [ "${UVICORN_WORKERS}" -gt 1 ] 2>/dev/null; then
  # re-evaluate DB path
  DB_PATH="${AUTH_DB_PATH:-/data/auth.db}"
  # read last PRAGMA result by opening a new connection and querying journal_mode
  python - <<'PY'
import os, sqlite3
db = os.getenv('AUTH_DB_PATH', '/data/auth.db')
ok = False
try:
    conn = sqlite3.connect(db)
    cur = conn.cursor()
    cur.execute('PRAGMA journal_mode')
    r = cur.fetchone()
    if r and r[0] == 'wal':
        ok = True
    print('[entrypoint] journal_mode check result:', r)
except Exception:
    import traceback
    print('[entrypoint] Failed to query journal_mode:')
    traceback.print_exc()
finally:
    try:
        conn.close()
    except Exception:
        pass
if not ok:
    print('[entrypoint] WARNING: SQLite WAL mode is not active. This may cause poor concurrent write performance with multiple workers.')
    print('[entrypoint] Common causes:')
    print('  - DB file is on a network/remote filesystem (NFS, SMB) that does not support SQLite shared-memory files (.db-shm/.db-wal).')
    print('  - File permissions prevent creation of -wal/-shm files.')
    print('Remediation suggestions:')
    print('  - Use a Docker named volume (as in docker-compose.yml: chat_data) instead of bind-mounting to an NFS/host path.')
    print('  - Ensure the container user can write to the DB directory and create files there.')
    print('  - For production, consider using Postgres or another client/server DB for robust concurrency.')
else:
    # check for presence of -wal and -shm files using the `db` variable
    wal = db + '-wal'
    shm = db + '-shm'
    has_wal = os.path.exists(wal)
    has_shm = os.path.exists(shm)
    print(f'[entrypoint] WAL/SHM files present: wal={has_wal}, shm={has_shm} (paths: {wal}, {shm})')
    if not (has_wal and has_shm):
        print('[entrypoint] NOTE: WAL was enabled but -wal/-shm files are not present. They may be created on demand by writers; if you expect heavy write concurrency, verify filesystem compatibility (avoid NFS/SMB).')
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
