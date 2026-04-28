import os
import subprocess
import sqlite3
from pathlib import Path


def _script_path():
    # repo root / docker-entrypoint.sh
    return str(Path(__file__).resolve().parents[2] / 'docker-entrypoint.sh')


def test_entrypoint_initializes_db(tmp_path, monkeypatch):
    db_path = tmp_path / 'auth_entry.db'
    env = os.environ.copy()
    env['AUTH_DB_PATH'] = str(db_path)
    script = _script_path()

    # Ensure the script runs (dry-run with 'true') and creates the DB
    res = subprocess.run(['/bin/bash', script, 'true'], env=env, cwd=str(Path(script).parent))
    assert res.returncode == 0
    assert db_path.exists()

    # Verify users table exists
    conn = sqlite3.connect(str(db_path))
    cur = conn.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users'")
    assert cur.fetchone() is not None
    conn.close()


def test_entrypoint_is_idempotent(tmp_path):
    db_path = tmp_path / 'auth_entry_idempotent.db'
    env = os.environ.copy()
    env['AUTH_DB_PATH'] = str(db_path)
    script = _script_path()

    # First run
    r1 = subprocess.run(['/bin/bash', script, 'true'], env=env, cwd=str(Path(script).parent))
    assert r1.returncode == 0
    assert db_path.exists()

    # Second run should also succeed and not break the DB
    r2 = subprocess.run(['/bin/bash', script, 'true'], env=env, cwd=str(Path(script).parent))
    assert r2.returncode == 0

    # DB still valid
    conn = sqlite3.connect(str(db_path))
    cur = conn.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users'")
    assert cur.fetchone() is not None
    conn.close()
