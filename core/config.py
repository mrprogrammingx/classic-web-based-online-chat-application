"""Centralized configuration backed by environment variables.

Use `core.config` for app-wide settings so values aren't hard-coded
throughout the codebase.
"""
import os
from pathlib import Path

# JWT settings (read once is fine)
JWT_SECRET = os.getenv('JWT_SECRET', 'change_this_secret')
JWT_ALGO = os.getenv('JWT_ALGO', 'HS256')

# Default durations (session expiry) and cookie name; these are not time
# sensitive for tests and may be read at import time.
SESSION_DEFAULT_EXPIRES_SECONDS = int(os.getenv('SESSION_DEFAULT_EXPIRES_SECONDS', str(60*60*24*7)))
SESSION_COOKIE_NAME = os.getenv('SESSION_COOKIE_NAME', 'token')


def _compute_db_path() -> str:
    """Compute DB path from environment at access time.

    Tests often monkeypatch AUTH_DB_PATH during collection; computing the
    path lazily ensures callers get the updated value when they import
    modules after setting the environment.
    """
    return os.getenv('AUTH_DB_PATH', str(Path.cwd() / 'auth.db'))


def _compute_presence_seconds() -> int:
    """Compute presence timeout from environment each time it's needed.

    Honor TEST_MODE (if set to '1') and enforce a minimum threshold when
    not in test mode so production runs don't accidentally use a tiny
    value.
    """
    try:
        _presence_env = int(os.getenv('PRESENCE_ONLINE_SECONDS', '60'))
    except Exception:
        _presence_env = 60
    _PRESENCE_MIN_SECONDS = 5
    # Enforce a sensible minimum so the server never uses an extremely
    # small presence timeout. Tests that require faster transitions should
    # explicitly adjust their expectations (or be authored to set the env
    # and verify behavior). Always enforce the minimum threshold here.
    return max(_presence_env, _PRESENCE_MIN_SECONDS)


def _compute_afk_seconds() -> int:
    """AFK timeout: a user with no tab interaction for this many seconds is
    considered AFK. Defaults to 60 (1 minute). Tests may override via env."""
    try:
        val = int(os.getenv('AFK_SECONDS', '60'))
    except Exception:
        val = 60
    return max(val, 5)  # enforce minimum 5s


def _compute_file_storage_path() -> str:
    """File storage path for uploads. Defaults to ./uploads directory."""
    return os.getenv('FILE_STORAGE_PATH', str(Path.cwd() / 'uploads'))


def _compute_max_file_size() -> int:
    """Maximum file size in bytes. Defaults to 20 MB."""
    try:
        val = int(os.getenv('MAX_FILE_SIZE_MB', '20'))
    except Exception:
        val = 20
    return val * 1024 * 1024  # Convert MB to bytes


def _compute_max_image_size() -> int:
    """Maximum image size in bytes. Defaults to 3 MB."""
    try:
        val = int(os.getenv('MAX_IMAGE_SIZE_MB', '3'))
    except Exception:
        val = 3
    return val * 1024 * 1024  # Convert MB to bytes


def __getattr__(name: str):
    # Provide lazy access to values that tests may override via env vars.
    if name == 'DB_PATH':
        return _compute_db_path()
    if name == 'PRESENCE_ONLINE_SECONDS':
        return _compute_presence_seconds()
    if name == 'AFK_SECONDS':
        return _compute_afk_seconds()
    if name == 'FILE_STORAGE_PATH':
        return _compute_file_storage_path()
    if name == 'MAX_FILE_SIZE_BYTES':
        return _compute_max_file_size()
    if name == 'MAX_IMAGE_SIZE_BYTES':
        return _compute_max_image_size()
    raise AttributeError(name)


__all__ = [
    'DB_PATH', 'JWT_SECRET', 'JWT_ALGO', 'PRESENCE_ONLINE_SECONDS',
    'AFK_SECONDS', 'SESSION_DEFAULT_EXPIRES_SECONDS', 'SESSION_COOKIE_NAME',
    'FILE_STORAGE_PATH', 'MAX_FILE_SIZE_BYTES', 'MAX_IMAGE_SIZE_BYTES'
]
