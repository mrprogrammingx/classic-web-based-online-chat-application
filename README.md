# Classic Web-Based Online Chat Application

A production-style web chat system built with **FastAPI + SQLite** supporting authentication, real-time presence, private messaging, file sharing, and moderation — designed for ~300 concurrent users.

✅ **Ready for Docker**: Fully containerized with `docker compose up`

# Quick Start (Docker)

```bash
# Clone repository
git clone https://github.com/mrprogrammingx/classic-web-based-online-chat-application.git
cd classic-web-based-online-chat-application

# Run with Docker Compose (single command!)
docker compose up
```

The app will start at **http://localhost:8000**

### Default Admin Credentials
- **Email**: admin@example.com
- **Username**: admin
- **Password**: admin

## Recent runtime and Docker improvements

This release includes a set of Docker/runtime fixes and improvements:

- Entrypoint DB initialization: the container runs `db.init_db()` at startup to ensure schema/migrations are applied before the server starts.
- WAL handling for multi-worker setups: when `UVICORN_WORKERS` > 1 the entrypoint attempts to enable SQLite WAL (PRAGMA journal_mode=WAL) and prints diagnostics. If WAL cannot be activated due to filesystem or permission issues the entrypoint logs clear warnings and guidance.
- Non-root runtime: the image creates a lightweight `app` user and the entrypoint will chown `/data` and `/app` and drop privileges to `app` where possible.
- Healthcheck without curl: `docker-compose.yml` uses a Python-based healthcheck so the image doesn't need `curl` installed.
- Tests: an integration test (`tests/test_entrypoint_wal.py`) was added to verify entrypoint WAL diagnostics.

See the rest of this README for usage, troubleshooting, and production notes.

## Verify It Works

1. Open http://localhost:8000 in your browser
2. You should see the login page
3. Login with admin/admin
4. Create a room or send a message
5. Open in another tab to test multi-tab presence

## Data Persistence & Volumes

By default the project uses a Docker named volume `chat_data` mounted at `/data` inside the container:

- `auth.db` — SQLite database (persisted in the `chat_data` volume)
- `uploads/` — User-uploaded files and images

Important notes about WAL and filesystems:

- SQLite WAL mode requires the filesystem to support SQLite shared-memory files (`-wal`, `-shm`). Named Docker volumes typically work well. Host bind-mounts, NFS/SMB, and some macOS host mounts may not support WAL or may prevent creation of the `-wal`/`-shm` files.
- The entrypoint logs whether WAL was enabled and whether `auth.db-wal`/`auth.db-shm` files are present. If you see warnings, prefer using the named volume (`chat_data`) or migrate to Postgres for production.

To reset data: `docker compose down -v` (removes volume)

## Features

- 👤 **User Accounts**: Registration, authentication, multi-device sessions
- 💬 **Chat Rooms**: Public discoverable + private invitation-only rooms
- 👥 **Personal Messaging**: One-to-one direct messages
- 🟢 **Presence Tracking**: Online/AFK/offline with multi-tab support
- 📁 **File Sharing**: Upload images and files (up to 20 MB)
- 🛡️ **Moderation**: Owner/admin roles, ban users, delete messages
- 💾 **Message History**: Persistent storage, infinite scroll support
- 🎨 **Clean UI**: Vanilla JavaScript, no heavy frameworks

## System Requirements

- **Docker & Docker Compose** (easiest)
- OR: Python 3.11+, pip, SQLite3

## Architecture

```
┌─────────────────────────────────┐
│   Frontend (Vanilla JS/HTML)    │
├─────────────────────────────────┤
│   FastAPI Backend               │
│   - Authentication (JWT)        │
│   - Chat Rooms & Messaging      │
│   - Presence Tracking           │
│   - File Management             │
├─────────────────────────────────┤
│   SQLite Database (Persistent)  │
│   Docker Volume: chat_data      │
└─────────────────────────────────┘
```

See [docs/architecture.md](./docs/architecture.md) for detailed architecture.

## Local Development (Without Docker)

```bash
# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run server (single-process dev server)
uvicorn app:app --reload --host 127.0.0.1 --port 8000
```

Then open http://localhost:8000

## Testing

### Run Tests with Docker

```bash
# Tests run automatically with TEST_MODE enabled in docker-compose.yml
docker compose up
```

### Run Tests Locally

```bash
# Install dev dependencies
pip install -r requirements-dev.txt

# Run all tests
pytest -q

# Run specific test suite
pytest -q tests/unit/test_presence_smoke.py
```

## Troubleshooting

### Port 8000 Already in Use

```bash
# Use a different port
docker run -p 8001:8000 <image>
# Or kill the existing process
lsof -nP -iTCP:8000 -sTCP:LISTEN
kill -9 <PID>
```

### SQLite WAL or DB Error on Startup

```bash
# If you see WAL warnings in the container logs, consider:
#  - Using the named Docker volume (default: chat_data) instead of a host bind-mount
#  - Ensuring the container user can create files in the DB directory
#  - For production, use Postgres instead of SQLite for robust concurrency
docker compose down -v
docker compose up
```

### Can't Login
- Username: admin  
   Password: admin
- Make sure app is fully started (check `docker compose logs`)
- Clear browser cache if stuck on login

### Docker Build Fails

```bash
# Clean build
docker compose down
docker system prune -a
docker compose up --build
```

## Environment Variables

| Variable | Default | Purpose |
|----------|---------|---------|
| `ADMIN_USER` | admin | Default admin username |
| `ADMIN_PASS` | admin | Default admin password |
| `AUTH_DB_PATH` | /data/auth.db | Database file location |
| `FILE_STORAGE_PATH` | /data/uploads | File upload directory |
| `TEST_MODE` | 1 | Enable test endpoints |
| `MAX_FILE_SIZE_MB` | 20 | Max file upload (MB) |
| `MAX_IMAGE_SIZE_MB` | 3 | Max image upload (MB) |
| `JWT_SECRET` | change_this_secret | JWT signing key (⚠️ change in production) |
| `PRESENCE_ONLINE_SECONDS` | 60 | Seconds before AFK status (min: 5) |

Override with environment:
```bash
ADMIN_PASS=SecurePassword123 docker compose up
```

## Project Structure

```
.
├── app.py                    # ASGI app entry point
├── init_admin.py             # Default admin creator
├── routers/                  # API endpoints
├── db/                       # Database layer
├── core/                     # Configuration & utilities
├── services/                 # Business logic
├── static/                   # Frontend assets
├── tests/                    # Test suite
├── Dockerfile                # Container image definition
├── docker-compose.yml        # Local development setup
├── requirements.txt          # Python dependencies
├── requirements-dev.txt      # Development dependencies
└── README.md                 # This file
```

## API Endpoints (Main Routes)

| Method | Endpoint | Purpose |
|--------|----------|---------|
| POST | `/register` | Create new user account |
| POST | `/login` | Authenticate user |
| POST | `/logout` | Logout current session |
| GET | `/me` | Get current user info |
| POST | `/password/reset-request` | Request password reset |
| POST | `/password/reset` | Reset password with token |
| PATCH | `/me/password` | Change password (authenticated) |
| DELETE | `/me` | Delete account |
| GET | `/rooms` | List public rooms |
| POST | `/rooms` | Create new room |
| POST | `/rooms/{id}/join` | Join room |
| POST | `/rooms/{id}/leave` | Leave room |
| POST | `/rooms/{id}/messages` | Send message to room |
| GET | `/rooms/{id}/messages` | Get room message history |
| GET | `/friends` | List contacts |
| POST | `/friends/request` | Send friend request |
| POST | `/friends/accept` | Accept friend request |
| POST | `/presence/heartbeat` | Update activity status |
| GET | `/sessions` | List active sessions |
| POST | `/sessions/revoke` | Logout specific device |

Full interactive API documentation: http://localhost:8000/docs (Swagger UI)

## Performance Targets

- ✅ Supports ~300 concurrent users
- ✅ Message delivery < 3 seconds
- ✅ Presence updates < 2 seconds
- ✅ Handles 10,000+ messages per room
- ✅ Multi-tab support with accurate presence
- ✅ File uploads up to 20 MB
- ✅ Image uploads up to 3 MB

## Production Deployment

For production deployments beyond Docker Compose:

1. **Security**n   - Set `JWT_SECRET` to a secure random string
   - Use environment-based credentials (never hardcode)
   - Enable HTTPS/SSL with reverse proxy (nginx/Apache)

2. **Database**
   - Use SQLite WAL mode for better concurrency
   - Set up regular backups of `auth.db`
   - Monitor database size (grows with message history)

3. **Storage**
   - Use persistent volume for `uploads/` directory
   - Consider S3/cloud storage for large deployments
   - Implement cleanup for old uploaded files

4. **Scaling**
   - Run multiple worker processes with Gunicorn
   - Use reverse proxy for load balancing
   - Consider caching layer (Redis) for sessions

5. **Monitoring**
   - Enable structured logging
   - Monitor disk usage (database + uploads)
   - Track concurrent user metrics

Example production docker-compose:
```yaml
services:
  web:
    image: chat-app:latest
    environment:
      JWT_SECRET: ${JWT_SECRET}
      ADMIN_USER: ${ADMIN_USER}
      ADMIN_PASS: ${ADMIN_PASS}
      AUTH_DB_PATH: /data/auth.db
      FILE_STORAGE_PATH: /data/uploads
    volumes:
      - chat_data:/data
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000"]
      interval: 30s
      timeout: 10s
```

## Contributing

When making changes:
1. Run tests locally: `pytest -q`
2. Check code imports: `flake8 --select=E999,F401`
3. Test with Docker: `docker compose up`
4. Ensure backward compatibility with existing databases

## Support & Documentation

- **Troubleshooting** → See [Troubleshooting](#troubleshooting) section above
- **Architecture** → See [docs/architecture.md](./docs/architecture.md)
- **Testing** → See [tests/README.md](./tests/README.md)
- **Development** → See [docs/development.md](./docs/development.md) (if available)

## Functional Requirements Implemented

- ✅ User registration and authentication
- ✅ Public and private chat rooms
- ✅ One-to-one personal messaging
- ✅ Contacts/friends system with confirmation
- ✅ File and image sharing with access control
- ✅ Moderation: owner/admin roles, message deletion, user bans
- ✅ Persistent message history with infinite scroll
- ✅ Multi-device session management
- ✅ Online/AFK/offline presence with multi-tab support
- ✅ Password reset and account deletion
- ✅ Unread message indicators

## Non-Functional Requirements Met

- ✅ Supports ~300 concurrent users
- ✅ Message delivery latency < 3 seconds
- ✅ Presence update latency < 2 seconds
- ✅ Persistent message storage (SQLite)
- ✅ Local file storage for uploads
- ✅ Session persistence across browser restarts
- ✅ Multi-tab browser support

---

**Ready to run?** → `docker compose up` 🚀

Questions? Check the [Troubleshooting](#troubleshooting) section or review the test files for usage examples.

