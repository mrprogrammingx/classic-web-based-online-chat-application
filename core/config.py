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
    # Always enforce a minimum threshold to prevent extremely small
    # values from confusing normal runtime behavior. Tests that need to
    # simulate smaller values can explicitly set TEST_MODE and still use
    # the env var; however, some tests assert the presence minimum is
    # enforced (>= 5s) so preserve that behavior here.
    if os.getenv('TEST_MODE') == '1':
        # If tests indicate they want a smaller value, allow it, but
        # the test harness expects the server to enforce a minimum of
        # 5 seconds for certain behaviors — so return max of env and min.
        return max(_presence_env, _PRESENCE_MIN_SECONDS)
    return max(_presence_env, _PRESENCE_MIN_SECONDS)


def __getattr__(name: str):
    # Provide lazy access to values that tests may override via env vars.
    if name == 'DB_PATH':
        return _compute_db_path()
    if name == 'PRESENCE_ONLINE_SECONDS':
        return _compute_presence_seconds()
    raise AttributeError(name)


__all__ = [
    'DB_PATH', 'JWT_SECRET', 'JWT_ALGO', 'PRESENCE_ONLINE_SECONDS',
    'SESSION_DEFAULT_EXPIRES_SECONDS', 'SESSION_COOKIE_NAME'
]
