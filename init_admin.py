"""Simple admin initializer called at app startup.

Creates a default admin user if none exists. Uses environment variables
ADMIN_USER and ADMIN_PASS if present; otherwise defaults to admin/admin123.

This module uses aiosqlite to match the project's DB access pattern and
is safe to call after `db.init_db()` has run.
"""
import os
import time
import logging
import aiosqlite
from core.utils import hash_pw
from typing import Optional

logger = logging.getLogger(__name__)


async def create_admin(username: Optional[str] = None, password: Optional[str] = None, db_path: Optional[str] = None):
    username = username or os.getenv('ADMIN_USER', 'admin')
    # Default password intentionally set to 'admin' to match common demo/dev
    # expectations; override via ADMIN_PASS in production or CI.
    password = password or os.getenv('ADMIN_PASS', 'admin')
    email = f"{username}@example.com"
    # Determine which DB path to use. Prefer explicit db_path if supplied
    # (used by tests). Otherwise import the project's db module so the
    # DB proxy resolution (and any test overrides) take effect.
    if db_path:
        target = db_path
    else:
        import db as db_mod
        target = db_mod.DB

    async with aiosqlite.connect(target) as db:
        try:
            cur = await db.execute('SELECT id FROM users WHERE is_admin = 1 LIMIT 1')
            row = await cur.fetchone()
        except Exception:
            # If the users table doesn't exist yet or DB is not ready,
            # we skip creation — init_db should have run before this call.
            logger.info('init_admin: users table not available, skipping admin creation')
            return

        if row:
            logger.info('init_admin: admin already exists (id=%s)', row[0])
            return

        try:
            await db.execute(
                'INSERT OR IGNORE INTO users (email, username, password, created_at, is_admin) VALUES (?, ?, ?, ?, ?)',
                (email, username, hash_pw(password), int(time.time()), 1)
            )
            await db.commit()
            logger.info('init_admin: created admin user %s (email=%s)', username, email)
            # Log password only when it was not supplied via env var
            if 'ADMIN_PASS' not in os.environ:
                logger.info('init_admin: admin password (generated/default): %s', password)
        except Exception:
            logger.exception('init_admin: failed to create admin')
