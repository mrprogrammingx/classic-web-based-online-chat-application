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

New admin tests
---------------
We added server-side filtering/search/pagination tests and cleanup tests for the
admin UI. They live in `tests/test_admin_user_cleanup.py` and
`tests/test_admin_search_and_pagination.py` and exercise:

- user deletion cascade cleanup (removes bans, sessions, memberships, messages)
- `/admin/users` server-side filtering (filter, q, page, per_page)
- `/admin/users/counts` for counts displayed on the admin UI

Run them the same way as other networked tests (server must be running):

```bash
uvicorn app:app --reload
.venv/bin/pytest -q tests/test_admin_user_cleanup.py tests/test_admin_search_and_pagination.py
```
