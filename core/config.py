"""Centralized configuration backed by environment variables.

Use `core.config` for app-wide settings so values aren't hard-coded
throughout the codebase.
"""
import os
from pathlib import Path

# Path to the sqlite DB file. Defaults to ./auth.db in the project root.
DB_PATH = os.getenv('AUTH_DB_PATH', str(Path.cwd() / 'auth.db'))

# JWT settings
JWT_SECRET = os.getenv('JWT_SECRET', 'change_this_secret')
JWT_ALGO = os.getenv('JWT_ALGO', 'HS256')

# Presence timeout (seconds) — used to determine online/AFK thresholds
# Presence timeout (seconds) — used to determine online/AFK thresholds
# Allow overriding via env, but enforce a sensible minimum so a tiny value
# (e.g. from a test config) doesn't mark active users AFK during normal use.
try:
    _presence_env = int(os.getenv('PRESENCE_ONLINE_SECONDS', '60'))
except Exception:
    _presence_env = 60
# minimum threshold in seconds
_PRESENCE_MIN_SECONDS = 5
PRESENCE_ONLINE_SECONDS = max(_presence_env, _PRESENCE_MIN_SECONDS)

# Default durations
SESSION_DEFAULT_EXPIRES_SECONDS = int(os.getenv('SESSION_DEFAULT_EXPIRES_SECONDS', str(60*60*24*7)))

# Cookie settings
SESSION_COOKIE_NAME = os.getenv('SESSION_COOKIE_NAME', 'token')

__all__ = [
    'DB_PATH', 'JWT_SECRET', 'JWT_ALGO', 'PRESENCE_ONLINE_SECONDS',
    'SESSION_DEFAULT_EXPIRES_SECONDS', 'SESSION_COOKIE_NAME'
]
