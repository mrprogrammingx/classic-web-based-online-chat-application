Testing
=======

This project contains two kinds of tests:

- Networked tests (default): tests that use real HTTP requests against a running
  local server at http://127.0.0.1:8000. These are simple and work with your
  project's current Python environment.
- Hermetic tests (fast): tests that use FastAPI's TestClient (in-process). These
  are faster and CI-friendly but require compatible dev packages and a
  supported Python version (we recommend Python 3.11 or 3.12).

Running networked tests
-----------------------

1. Start the server:

```bash
uvicorn app:app --reload
```

2. Run tests (they will be skipped if the server is not reachable):

```bash
.venv/bin/pytest -q
```

Running hermetic tests (recommended for CI)
-------------------------------------------

1. Use a supported Python interpreter (3.11 or 3.12) and create a venv.
2. Install dev deps:

```bash
.venv/bin/pip install -r requirements-dev.txt
```

3. Run tests (in-process):

```bash
.venv/bin/pytest -q
```

Notes
-----
- If TestClient fails due to httpx/httpcore compatibility, use Python 3.11/3.12
  for hermetic runs or run the networked tests instead.
