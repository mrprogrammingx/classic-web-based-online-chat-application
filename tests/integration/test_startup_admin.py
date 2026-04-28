import asyncio
import os
import tempfile
from pathlib import Path


def setup_temp_db(tmp_path):
    db_path = str(tmp_path / 'test_startup_admin.db')
    import db
    db.DB = db_path
    import db.schema as schema
    schema.DB = db_path
    asyncio.run(db.init_db())
    return db_path


def test_startup_creates_admin(tmp_path, monkeypatch):
    # Prepare an isolated DB
    db_path = setup_temp_db(tmp_path)

    # Ensure default envs are not set so create_admin uses defaults
    monkeypatch.delenv('ADMIN_USER', raising=False)
    monkeypatch.delenv('ADMIN_PASS', raising=False)

    # Import the initializer and run it against the test DB
    from init_admin import create_admin

    # Run startup helper (synchronous wrapper around async call)
    asyncio.run(create_admin(db_path=db_path))

    # Verify admin was created
    import aiosqlite

    async def _check():
        async with aiosqlite.connect(db_path) as conn:
            cur = await conn.execute('SELECT username, is_admin FROM users WHERE username = ?', ('admin',))
            row = await cur.fetchone()
            return row

    row = asyncio.run(_check())
    assert row is not None and row[0] == 'admin' and row[1] == 1
