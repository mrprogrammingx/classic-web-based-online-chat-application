# Classic Web-Based Online Chat Application

A FastAPI-based classic web chat application with SQLite persistence, comprehensive user authentication, real-time presence tracking, friends/contacts system, private messaging, file sharing, and moderation features. Designed for moderate-scale deployments supporting up to 300 simultaneously connected users.

## Overview

This application implements a **classic web chat experience** with straightforward navigation and standard chat features:

- 👤 **User Accounts**: Registration, authentication, password management, session management across multiple devices
- 💬 **Chat Rooms**: Public discoverable rooms and private invitation-only rooms with flexible membership
- 👥 **Personal Messaging**: One-to-one direct messaging between friends with the same features as room chats
- 📋 **Contacts/Friends**: Friend list with friendship confirmation workflow and user-to-user blocking
- 🟢 **Presence Tracking**: Real-time online/AFK/offline status with multi-tab support (user is online if any tab is active)
- 📁 **File Sharing**: Image and file uploads with access control (up to 20 MB files, 3 MB images)
- 🔔 **Notifications**: Unread message indicators with low-latency updates
- 🛡️ **Moderation**: Room admins and owners with controls for message deletion, member removal, and user banning
- 💾 **Persistent History**: Full message history with infinite scroll support for years of chat data

---

## Functional Requirements

### 1. User Accounts and Authentication

#### Registration
- Users self-register with: email, password, unique username
- Email and username must be unique
- Username is immutable after registration
- Email verification is not required

#### Authentication
- Sign in with email and password
- Persistent login across browser close/reopen (session-based)
- Sign out from current browser (does not affect other active sessions)
- Password reset and password change capabilities
- Passwords stored securely in hashed form

#### Account Management
- Users may delete their own account
- Account deletion removes only chat rooms owned by that user
- Messages, files, and images in deleted rooms are deleted permanently
- Membership in other rooms is automatically removed

### 2. User Presence and Sessions

#### Presence States
- **Online**: User is actively using the application in at least one browser tab
- **AFK** (Away From Keyboard): User has open tabs but no interaction for > 1 minute
- **Offline**: No open browser tabs with the application

#### Multi-Tab Support
- Same user can open chat in multiple browser tabs simultaneously
- User appears **online** if active in at least one tab
- **AFK** only when all open tabs have been inactive for > 1 minute
- User shows **offline** only when all browser tabs are closed/unloaded

#### Active Sessions
- Users can view list of active sessions with browser/IP details
- Users can log out selected sessions from any device
- Logging out from current browser invalidates only that session
- Other active sessions remain valid

### 3. Contacts and Friends

#### Friend List
- Each user has a personal contact/friend list
- Friend requests may include optional text message

#### Friendship Confirmation
- Friend requests require confirmation by recipient
- Users may send friend requests by username
- Users may send friend requests from room member lists

#### Friend Management
- Users may remove friends from their list
- Users may ban other users (blocks all contact in both directions)

#### User-to-User Ban
- Banned user cannot contact the user who banned them in any way
- Existing personal message history remains visible but becomes read-only
- Friend relationship is effectively terminated
- Personal messaging is blocked in both directions

### 4. Chat Rooms

#### Room Creation and Properties
- Any registered user may create a chat room
- Each room has: name, description, visibility (public/private), owner, admins, members, banned users list
- Room names are unique

#### Public Rooms
- Discoverable in public catalog showing: name, description, member count
- Catalog supports simple substring search
- Can be joined freely by any authenticated user unless banned

#### Private Rooms
- Not visible in public catalog
- Accessible only by invitation from room members

#### Room Membership
- Users may freely join public rooms (unless banned)
- Users may freely leave rooms
- Owner cannot leave their own room (only can delete it)
- Users may invite others to private rooms

#### Room Deletion
- Only room owner can delete room
- All messages in room are deleted permanently
- All files and images in room are deleted permanently

#### Owner and Admin Roles

**Owner** (always an admin):
- Cannot lose admin privileges
- Can delete the room
- Can remove any admin (including other admins, but not themselves)
- Can remove any member
- All admin capabilities

**Admins** (except owner):
- Delete messages in the room
- Remove members from the room
- Ban members from the room
- View banned users list and who banned each user
- Remove users from ban list
- Can be removed from admin status by owner

#### Room Ban Rules
- When user is removed from room, they are banned
- Banned users cannot rejoin unless removed from ban list
- Banned users lose access to room messages and files through UI
- Files remain stored unless room is deleted

### 5. Messaging

#### Message Features
- Plain text and multiline messages
- UTF-8 support with emoji
- File and image attachments
- Reply/reference to another message
- Maximum text size: 3 KB per message

#### Message Operations
- **Compose**: Multiline text entry with emoji and attachment support
- **Edit**: Users can edit their own messages (shows "edited" indicator)
- **Delete**: Message author or room admins can delete
- **Reply**: Reply to messages with visual reference in UI
- **Order**: Chronological display with infinite scroll for history

#### Message Delivery
- Messages sent to offline users are persisted and delivered upon next login
- Messages display in chronological order
- Full history available with infinite scroll

### 6. Attachments (File and Image Sharing)

#### Supported Types
- Images (with 3 MB limit)
- Arbitrary file types (with 20 MB limit)

#### Upload Methods
- Explicit upload button
- Copy and paste

#### Attachment Metadata
- Original filename preserved
- Optional comment can be added

#### Access Control
- Files/images only downloadable by current chat members or authorized personal chat participants
- Users losing access to room also lose access to room files/images
- Files persist after upload unless room is deleted

### 7. Notifications

#### Unread Indicators
- Visual indicators show unread messages in:
  - Chat rooms
  - Personal dialogs
- Unread count near room/contact names
- Cleared when user opens corresponding chat

#### Presence Update Speed
- Online/AFK/offline presence updates appear with low latency (< 2 seconds)

---

## Non-Functional Requirements

### Capacity and Scale
- Support up to **300 simultaneous users**
- Single room can contain up to **1000 participants**
- Users may belong to **unlimited rooms**
- Typical user has ~20 rooms and ~50 contacts

### Performance
- Message delivery latency: **< 3 seconds** after sending
- Presence update latency: **< 2 seconds**
- Application remains usable with very large room history (10,000+ messages)

### Persistence
- Messages stored persistently for years
- Full chat history available with infinite scroll
- Session state persists across browser close/reopen

### File Storage
- **Location**: Local file system
- **Max file size**: 20 MB
- **Max image size**: 3 MB

### Session Behavior
- No automatic logout due to inactivity
- Login state persists across browser close/open
- Works correctly across multiple tabs for same user

### Reliability
- Consistent preservation of:
  - Membership data
  - Room ban lists
  - File access rights
  - Message history
  - Admin/owner permissions

---

## Technical Stack

- **Backend**: FastAPI (Python async)
- **Database**: SQLite with persistent file storage
- **Frontend**: Vanilla JavaScript with HTML5
- **Authentication**: JWT tokens (HttpOnly cookies)
- **Presence**: Polling-based system with automatic stale tab cleanup
- **File Storage**: Local filesystem with configurable paths and size limits
- **Testing**: pytest (unit/integration), Playwright (E2E)

---

## Quick Start

### Prerequisites
- Python 3.7+
- Node.js 14+ (for Playwright E2E tests)

### Installation

1. Clone and setup Python environment:
```bash
python3 -m venv .venv
source .venv/bin/activate
```

2. Install Python dependencies:
```bash
pip install -r requirements.txt
pip install -r requirements-dev.txt
```

3. Install Node.js dependencies (for E2E tests):
```bash
npm ci
npx playwright install
```

### Running

**Development server** (with auto-reload):
```bash
uvicorn app:app --reload --port 8000
```

**Production server**:
```bash
uvicorn app:app --host 0.0.0.0 --port 8000 --workers 4
```

### Testing

**Unit and integration tests**:
```bash
pytest -q
pytest -q tests/unit/test_presence_smoke.py       # Presence system (19 tests)
pytest -q tests/unit/test_tab_cleanup.py          # Stale tab cleanup (5 tests)
pytest -q tests/unit/test_file_storage_config.py  # File storage config (8 tests)
```

**End-to-end browser tests** (requires running server on port 8000):
```bash
# Terminal 1: Start server with TEST_MODE enabled
export TEST_MODE=1
uvicorn app:app --reload --port 8000

# Terminal 2: Run E2E tests
npx playwright test
npx playwright test tests/e2e/playwright/presence_ui.spec.js
```

---

## Configuration

### Environment Variables

#### Authentication & Session
- `JWT_SECRET`: Secret key for JWT signing (default: 'change_this_secret')
- `JWT_ALGO`: JWT algorithm (default: 'HS256')
- `SESSION_DEFAULT_EXPIRES_SECONDS`: Session duration in seconds (default: 604800 = 7 days)
- `SESSION_COOKIE_NAME`: Cookie name for session token (default: 'token')

#### Database
- `AUTH_DB_PATH`: Path to SQLite database (default: './auth.db')

#### Presence Tracking
- `PRESENCE_ONLINE_SECONDS`: Seconds of inactivity before AFK status (default: 60, minimum: 5)
- `AFK_SECONDS`: Alias for above (default: 60, minimum: 5)

#### File Storage
- `FILE_STORAGE_PATH`: Directory for uploaded files (default: './uploads')
- `MAX_FILE_SIZE_MB`: Maximum file upload size in MB (default: 20)
- `MAX_IMAGE_SIZE_MB`: Maximum image upload size in MB (default: 3)

#### Testing
- `TEST_MODE=1`: Enables test-only endpoints like `POST /_test/create_user`

### Example Configuration

```bash
# Production setup
export JWT_SECRET="your-secure-secret-here"
export AUTH_DB_PATH="/var/lib/chat/auth.db"
export FILE_STORAGE_PATH="/var/lib/chat/uploads"
export MAX_FILE_SIZE_MB=50
export MAX_IMAGE_SIZE_MB=10
export PRESENCE_ONLINE_SECONDS=60

uvicorn app:app --host 0.0.0.0 --port 8000 --workers 4
```

---

## Architecture

### Directory Structure

```
.
├── core/                    # Configuration and utilities
│   ├── config.py           # Centralized config (environment variables)
│   ├── logging_setup.py    # Logging configuration
│   └── utils.py            # Auth, presence, session utilities
├── routers/                 # API endpoints
│   ├── users.py            # User registration, password, account
│   ├── auth.py             # Authentication endpoints
│   ├── presence.py         # Presence/heartbeat endpoints
│   ├── rooms.py            # Chat room endpoints
│   ├── messages.py         # Message posting/retrieval
│   ├── friends.py          # Friends/contacts endpoints
│   ├── sessions.py         # Active session management
│   └── admin.py            # Admin endpoints
├── services/               # Business logic
│   ├── friends_service.py  # Friend operations
│   └── admin_service.py    # Admin operations
├── static/                 # Frontend assets
│   ├── app/               # JavaScript app logic
│   └── styles.css         # Styling
├── db/                     # Database schema
│   ├── schema.py          # Database initialization
│   └── __init__.py
├── tests/                  # Test suite
│   ├── unit/              # Unit and integration tests
│   └── e2e/               # End-to-end tests
├── app.py                 # FastAPI application entry point
├── rooms.py               # Room business logic (legacy)
├── admin.py               # Admin utilities (legacy)
└── requirements.txt       # Python dependencies
```

### Key Features Implemented

#### ✅ Presence System
- Real-time online/AFK/offline tracking
- Multi-tab support with activity-based state
- Automatic cleanup of stale tab records (> 24 hours inactive)
- 2-second polling interval for UI updates

#### ✅ Friends and Contacts
- Friend request workflow with confirmation
- User-to-user blocking/banning
- Friend request messaging

#### ✅ Chat Rooms
- Public and private room support
- Owner and admin role management
- Member and ban list management
- Message moderation

#### ✅ File Storage
- Configurable upload paths and size limits
- Access control based on room/chat membership
- File persistence with room deletion cleanup

#### ✅ Sessions
- Multi-device session management
- Per-session logout capability
- HttpOnly JWT cookies for security

#### ✅ Messages
- Text and multiline message support
- Emoji support
- Message editing and deletion
- Message replies/references
- Infinite scroll history

---

## API Reference

### Core Endpoints

#### Authentication
- `POST /users/register` - User registration
- `POST /users/login` - User login
- `POST /users/logout` - Logout current session
- `POST /users/password/reset` - Password reset
- `POST /users/password/change` - Change password (authenticated)
- `DELETE /users/account` - Delete user account

#### Presence
- `POST /presence/heartbeat` - Update user presence/activity
- `GET /presence/{user_id}` - Get user presence status
- `GET /presence?ids=1,2,3` - Get batch presence statuses

#### Chat Rooms
- `POST /rooms` - Create new room
- `GET /rooms` - List public rooms with search
- `GET /rooms/{room_id}` - Get room details
- `POST /rooms/{room_id}/join` - Join room
- `POST /rooms/{room_id}/leave` - Leave room
- `DELETE /rooms/{room_id}` - Delete room (owner only)
- `POST /rooms/{room_id}/messages` - Send message
- `GET /rooms/{room_id}/messages` - Get room messages

#### Messages
- `PATCH /messages/{message_id}` - Edit message
- `DELETE /messages/{message_id}` - Delete message

#### Friends
- `POST /friends/request` - Send friend request
- `POST /friends/accept` - Accept friend request
- `DELETE /friends/{friend_id}` - Remove friend
- `POST /friends/{friend_id}/ban` - Ban user
- `POST /friends/{friend_id}/unban` - Unban user
- `GET /friends` - Get friends list

#### Sessions
- `GET /sessions` - List active sessions
- `POST /sessions/revoke` - Logout specific session

#### Admin
- `POST /rooms/{room_id}/ban` - Ban user from room
- `POST /rooms/{room_id}/unban` - Unban user from room
- `POST /rooms/{room_id}/admins/add` - Add room admin
- `POST /rooms/{room_id}/admins/remove` - Remove room admin
- `DELETE /rooms/{room_id}/messages/{message_id}` - Admin delete message

---

## Recent Implementations

### Stale Tab Cleanup (March 2026)
Fixed issue where users remained AFK after closing all browser tabs. Added automatic cleanup of tab records inactive for > 24 hours, ensuring accurate offline detection. See `STALE_TAB_CLEANUP_FIX.md`.

### File Storage Configuration (March 2026)
Added centralized file storage configuration for managing upload locations and file size limits. See `FILE_STORAGE_IMPLEMENTATION.md`.

---

## Troubleshooting

### Server Won't Start
```bash
# Check if port 8000 is in use
lsof -nP -iTCP:8000 -sTCP:LISTEN

# Kill stale uvicorn processes
pkill -f uvicorn
```

### Database Errors
```bash
# Reset database (deletes local data)
rm -f auth.db
```

### Tests Failing
```bash
# Ensure using project virtualenv
source .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt

# Run with verbose output
pytest -vv tests/unit/test_presence_smoke.py
```

### Playwright Tests Not Finding Server
```bash
# Start server in separate terminal with TEST_MODE enabled
export TEST_MODE=1
uvicorn app:app --reload --port 8000

# Then run Playwright tests
npx playwright test
```

---

## Development

### Running Tests Locally

All tests:
```bash
pytest -q
```

Specific test categories:
```bash
pytest -q tests/unit/test_presence_smoke.py       # Presence system (19 tests)
pytest -q tests/unit/test_tab_cleanup.py          # Stale tab cleanup (5 tests)
pytest -q tests/unit/test_file_storage_config.py  # File storage config (8 tests)
```

Playwright E2E tests:
```bash
npx playwright test tests/e2e/playwright/presence_ui.spec.js
npx playwright test tests/e2e/playwright/home_features.spec.js
```

### Code Style and Linting

```bash
# Check imports
flake8 --select=E999,F401 app.py routers/ core/ services/

# Type checking (optional)
mypy app.py --ignore-missing-imports
```

---

## License

This project is part of the HackTheWorkflow initiative.

---

## Support and Contributing

For issues, questions, or contributions:
- Check the troubleshooting section above
- Review test files for usage examples
- Examine endpoint implementations in `routers/` directory
- Check configuration options in `core/config.py`
