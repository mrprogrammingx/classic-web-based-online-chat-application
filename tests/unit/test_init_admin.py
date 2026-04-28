import asyncio
import os
import aiosqlite


def setup_temp_db(tmp_path):
    db_path = str(tmp_path / 'test_init_admin.db')
    import db
    db.DB = db_path
    import db.schema as schema
    schema.DB = db_path
    asyncio.run(db.init_db())
    return db_path


def get_admin_rows(db_path):
    async def _g():
        async with aiosqlite.connect(db_path) as conn:
            cur = await conn.execute('SELECT id, username, email, is_admin FROM users')
            rows = await cur.fetchall()
            return rows
    return asyncio.run(_g())


def test_create_admin_idempotent(tmp_path, monkeypatch):
    db_path = setup_temp_db(tmp_path)

    # Ensure env not set for this test
    monkeypatch.delenv('ADMIN_USER', raising=False)
    monkeypatch.delenv('ADMIN_PASS', raising=False)

    from init_admin import create_admin

    # Call twice (should not create duplicates)
    asyncio.run(create_admin(db_path=db_path))
    asyncio.run(create_admin(db_path=db_path))

    rows = get_admin_rows(db_path)
    # Only one admin user row should exist
    admins = [r for r in rows if r[3] == 1]
    assert len(admins) == 1
    assert admins[0][1] == 'admin'


def test_create_admin_respects_env_vars(tmp_path, monkeypatch):
    db_path = setup_temp_db(tmp_path)

    monkeypatch.setenv('ADMIN_USER', 'superadmin')
    monkeypatch.setenv('ADMIN_PASS', 'supersecret')

    from init_admin import create_admin

    asyncio.run(create_admin(db_path=db_path))

    rows = get_admin_rows(db_path)
    admins = [r for r in rows if r[3] == 1]
    assert len(admins) == 1
    assert admins[0][1] == 'superadmin'
