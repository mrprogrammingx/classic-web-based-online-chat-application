# classic-web-based-online-chat-application

Lightweight FastAPI-based demo of a web chat backend focused on authentication, per-session JWTs, and multi-tab presence. This repository is intended as a small, runnable example (SQLite) and contains a minimal static demo UI under `/static`.

## Features implemented
- User registration and login (passwords hashed with passlib/pbkdf2_sha256)
- JWT tokens with per-session identifiers (jti) and session rows in SQLite for per-session revocation
- Persistent login using HttpOnly cookie + `/refresh` endpoint
- Per-session logout (invalidates current session only)
- Password reset (demo token), password change, and account deletion with cleanup of rooms/messages/memberships/sessions
- Multi-tab presence tracking (online / AFK / offline) using per-tab heartbeats and a `tab_presence` table
- Session listing and session revoke endpoints
- Admin endpoints: list users, delete user, promote user to admin
- Minimal static demo UI (`/static/index.html`, `static/main.js`) with heartbeat and admin modal
- Small management CLI to create/promote/delete users: `scripts/manage_users.py` and `scripts/add_admin.sh`
- Integration tests (pytest) that exercise register/login/presence flows (`tests/test_presence_api.py`)

## Quick start (local development)
Prerequisites: Python 3.11+, virtualenv recommended.

1. Create and activate a virtualenv (example):

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

2. Start the server:

```bash
.venv/bin/uvicorn app:app --reload
```

3. Open the demo UI in your browser:

- http://127.0.0.1:8000/

4. Create an admin (optional):

```bash
./scripts/add_admin.sh admin@example.com admin Secret123!
# or
python3 scripts/manage_users.py create --email admin@example.com --username admin --password Secret123! --admin
```

## Important endpoints
- POST /register — register user (returns token and sets cookie)
- POST /login — login (returns token and sets cookie)
- POST /logout — logout current session (removes session row and cookie)
- POST /refresh — renew token and extend session expiry
- GET /sessions — list current user's active sessions (requires auth)
- POST /sessions/revoke — revoke a session by jti (requires auth)
- POST /presence/heartbeat — tab heartbeat (tab_id + jti)
- POST /presence/close — notify server a tab closed
- GET /presence/{user_id} — get presence status for a user
- GET /admin/users — list users (admin only)
- POST /admin/users/promote — promote user to admin (admin only)
- POST /admin/users/delete — delete a user (admin only)

## Tests
Run the integration tests (requires server running on http://127.0.0.1:8000):

```bash
pytest -q
```

## Notes and next steps
- Persistence is SQLite for demo purposes. For production, consider Postgres for data and Redis for presence/session TTLs.
- Consider adding CSRF protection and Secure cookies when deploying behind HTTPS.
- Add automated migrations (Alembic) and CI workflow to run tests and format/lint checks.

If you want, I can convert integration tests to non-networked TestClient tests, add CI (GitHub Actions), or migrate presence to Redis.
