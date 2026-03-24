import sys
import pathlib
import os

# ensure project root is on sys.path so tests can import project modules if needed
ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pytest
import subprocess
import time
import requests
import socket
import typing


def _wait_for_port(host, port, timeout=5.0):
    start = time.time()
    while time.time() - start < timeout:
        try:
            with socket.create_connection((host, port), timeout=1):
                return True
        except Exception:
            time.sleep(0.1)
    return False


# Tests rely on environment variables for test-only configuration.
# Set PRESENCE_ONLINE_SECONDS in your shell or CI before running pytest, e.g.:
# PRESENCE_ONLINE_SECONDS=3 pytest -q


@pytest.fixture(scope='session')
def server():
    """Start the uvicorn server as a background process for tests, tear down at session end."""
    # load test env file if present so subprocess inherits test-only env vars
    env_file = ROOT / '.env.test'
    if env_file.exists():
        try:
            with env_file.open('r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith('#'):
                        continue
                    if '=' in line:
                        k, v = line.split('=', 1)
                        os.environ.setdefault(k.strip(), v.strip())
        except Exception:
            # ignore malformed env files
            pass

    # redirect server stdout/stderr to a logfile so tests can inspect server tracebacks
    logf = open('/tmp/test_uvicorn.log', 'wb')
    # PRESENCE_ONLINE_SECONDS will be set in pytest_configure from pytest.ini (or defaults)
    # use the same Python interpreter so installed packages (fastapi, passlib, etc.) are available
    proc = subprocess.Popen([sys.executable, '-m', 'uvicorn', 'app:app', '--port', '8000'], stdout=logf, stderr=logf)
    ok = _wait_for_port('127.0.0.1', 8000, timeout=5.0)
    if not ok:
        proc.kill()
        raise RuntimeError('server failed to start on port 8000')
    yield
    proc.terminate()
    try:
        proc.wait(timeout=2)
    except Exception:
        proc.kill()
    try:
        logf.close()
    except Exception:
        pass


@pytest.fixture
def client(server):
    """Return a requests.Session configured for the test server."""
    s = requests.Session()
    s.base_url = 'http://127.0.0.1:8000'
    # helper convenience: add a .post/.get wrapper that accepts path
    class C:
        def __init__(self, s):
            self.s = s
            self.base = s.base_url

        def post(self, path, **kwargs):
            return self.s.post(self.base + path, **kwargs)

        def get(self, path, **kwargs):
            return self.s.get(self.base + path, **kwargs)
        
        def delete(self, path, **kwargs):
            return self.s.delete(self.base + path, **kwargs)

    return C(s)
