import os
import subprocess
import tempfile
import textwrap


def test_entrypoint_enables_wal_and_reports(tmp_path):
    """Run docker-entrypoint.sh with UVICORN_WORKERS=4 and a temporary
    AUTH_DB_PATH to validate the script attempts to enable WAL and emits
    diagnostic messages.
    """
    # create temp db path inside tmp_path
    db_file = tmp_path / "auth.db"
    # ensure parent exists
    db_file.parent.mkdir(parents=True, exist_ok=True)

    env = os.environ.copy()
    env["UVICORN_WORKERS"] = "4"
    env["AUTH_DB_PATH"] = str(db_file)
    # Force Python to use the repository root so imports in the entrypoint's
    # embedded python blocks can find local modules like `db`.
    env["PYTHONPATH"] = os.getcwd()

    # Run the entrypoint script but pass a harmless command so exec finishes.
    cmd = ["bash", "docker-entrypoint.sh", "echo", "ok"]

    proc = subprocess.run(cmd, env=env, cwd=os.getcwd(), capture_output=True, text=True, timeout=60)

    # Ensure the script completed successfully and returned the final exec output
    assert proc.returncode == 0, f"entrypoint exited non-zero: stdout={proc.stdout!r} stderr={proc.stderr!r}"

    out = proc.stdout + proc.stderr

    # Look for evidence the entrypoint attempted to enable WAL and performed a journal_mode check
    assert "PRAGMA journal_mode result" in out or "journal_mode check result" in out, (
        "Expected WAL-related diagnostics in entrypoint output; got:\n" + out
    )
