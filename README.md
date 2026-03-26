# Classic Web Chat (small README)

A small FastAPI chat backend (SQLite) with registration, per-session JWTs, presence, friends/bans, private messaging, and chat rooms (public + private).

This README shows how to set up, run, and test locally and documents the rooms behavior and troubleshooting tips.

## Quick start

1. Create and activate a virtualenv in the repo root:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

2. Install dependencies:

```bash
.venv/bin/pip install -r requirements.txt
.venv/bin/pip install -r requirements-dev.txt
```

3. Run the development server:

```bash
.venv/bin/uvicorn app:app --reload --port 8000
```

4. Run the test suite (the test fixture will start a test server on 127.0.0.1:8000):

```bash
.venv/bin/pytest -q
```

Run a single test file:

```bash
.venv/bin/pytest -q tests/test_public_rooms_catalog.py -q
```

## Rooms API (high level)

- POST /rooms — create a room. Body: { name, description?, visibility? } (visibility is `public` or `private`). Owner is automatically a member and admin.
- GET /rooms — public rooms catalog. Supports `q` (substring search), `limit`, `offset`. Each item includes `member_count`.
- GET /rooms/{room_id} — room details (owner_id, admins, members (IDs), bans). Private rooms require membership to view.
- POST /rooms/{room_id}/join — join a public room (banned users blocked). Private rooms cannot be joined without invitation.
- POST /rooms/{room_id}/leave — leave a room. The owner cannot leave their own room (403).
- DELETE /rooms/{room_id} — owner-only: delete the room.
- POST /rooms/{room_id}/members/add — owner/admin can add (invite) users to a private room.
- POST /rooms/{room_id}/admins/add and /admins/remove — manage admins.
- POST /rooms/{room_id}/ban and /unban — ban/unban users (bans remove membership/admin status).
- POST /rooms/{room_id}/messages and GET /rooms/{room_id}/messages — post/list messages. Posting rules:
  - public rooms: any registered user may post unless banned
  - private rooms: only members may post

## Important semantics

- Private rooms do not appear in the public catalog and are accessible only to invited members.
- The owner cannot leave their own room. Only the owner may delete the room.
- Banning a user from a room removes them from members and admins; they must be unbanned and re-added.

## Troubleshooting

- If pytest fails because uvicorn won't start or you see 404s/500s, check the test server log written by the test fixture:

```bash
tail -n 200 /tmp/test_uvicorn.log || true
```

- If you see ModuleNotFoundError (e.g. `passlib`), ensure you run pytest using the project virtualenv Python:

```bash
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/pytest -q
```

- If port 8000 is occupied by another server, stop it before running tests or kill stale uvicorn processes:

```bash
lsof -nP -iTCP:8000 -sTCP:LISTEN || true
pkill -f uvicorn || true
```

- If you encounter SQLite schema errors, remove the `auth.db` and let the app re-create it during tests (this deletes local data):

```bash
rm -f auth.db
.venv/bin/pytest -q
```

## Development notes

- DB migrations: the app runs a small migration step on startup (safe ALTERs) to support older DB files.
- Tests: use the `tests/conftest.py` fixture which starts uvicorn as a subprocess under the invoking Python.

If you'd like, I can add a CI workflow (GitHub Actions), improve search (case-insensitive or SQLite FTS), or add a member listing endpoint with user details.

## Playwright (browser) E2E tests

Quick notes for running the Playwright end-to-end tests that exercise the real UI (the project contains a Playwright spec at `tests/e2e/playwright/reply_preview.spec.js` and a small helper at `tests/e2e/playwright/helpers.js`).

- Prerequisites: Node.js + npm (for Playwright), and the project Python virtualenv (see Quick start above).
- Install JS dependencies:

```bash
npm ci
# or: npm install
```

- Install Playwright browsers (required once per machine):

```bash
npx playwright install
```

- Start the server locally in a separate terminal (the tests expect the app at http://127.0.0.1:8000):

```bash
.venv/bin/uvicorn app:app --reload --port 8000
```

- Run the single Playwright spec:

```bash
npx playwright test tests/e2e/playwright/reply_preview.spec.js
# or via npm script if present: npm run test:playwright
```

Notes:
- The Playwright spec uses the API to register users and sets the server-issued HttpOnly `token` cookie directly in the browser context to avoid interactive login. That helper is in `tests/e2e/playwright/helpers.js`.
- The CI workflow at `.github/workflows/playwright.yml` in this repo runs the same spec on pushes/PRs. The workflow starts a uvicorn server in the background before running Playwright.
- If tests fail because the server isn't ready, wait for `http://127.0.0.1:8000` to respond or increase the startup sleep/probe in CI.

Test-mode note (required for deterministic test user creation)
---------------------------------------------------------

Some Playwright specs use a test-only server helper endpoint (`POST /_test/create_user`) to create users deterministically and return an auth token. That endpoint is only exposed when the server process is started with the environment variable `TEST_MODE=1` (this prevents exposing test helpers in production).

To run Playwright tests locally against a server started with the test helpers enabled, either:

1) Start the server manually with TEST_MODE enabled in a separate terminal:

```bash
export TEST_MODE=1
.venv/bin/uvicorn app:app --reload --port 8000
```

or

2) Ensure the pytest-based test harness which launches uvicorn sets `TEST_MODE=1` in its environment (the repository's `tests/conftest.py` sets this automatically when running the pytest harness). When relying on the pytest harness, run the Playwright specs via the test runner so the fixture starts the server with TEST_MODE enabled.

If `/_test/create_user` returns 404 during tests, that usually means the server process wasn't started with `TEST_MODE=1`.

If you'd like, I can add Playwright fixtures (for shared setup/teardown), collect traces/screenshots on failure, and upload those artifacts from CI for easier debugging.
