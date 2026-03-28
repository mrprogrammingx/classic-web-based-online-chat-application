import asyncio
import aiosqlite
import os
from typing import Dict


def setup_temp_db(tmp_path):
    db_path = str(tmp_path / 'test_admin_extra.db')
    import db
    db.DB = db_path
    import db.schema as schema
    schema.DB = db_path
    asyncio.run(db.init_db())
    return db_path


async def _insert_users(db_path: str):
    async with aiosqlite.connect(db_path) as conn:
        await conn.execute("INSERT INTO users (email, username, password, created_at) VALUES (?, ?, ?, ?)", ('a@example.com', 'alice', 'pw', 1))
        await conn.execute("INSERT INTO users (email, username, password, created_at) VALUES (?, ?, ?, ?)", ('b@example.com', 'bob', 'pw', 2))
        await conn.commit()


def insert_users(db_path: str):
    asyncio.run(_insert_users(db_path))


def get_user_ids(db_path: str) -> Dict[str, int]:
    async def _g():
        async with aiosqlite.connect(db_path) as conn:
            cur = await conn.execute('SELECT id, username FROM users')
            rows = await cur.fetchall()
            return {r[1]: r[0] for r in rows}
    return asyncio.run(_g())


def test_ban_and_unban_user(tmp_path):
    db_path = setup_temp_db(tmp_path)
    insert_users(db_path)

    from services import admin_service

    ids = get_user_ids(db_path)
    alice = ids['alice']
    bob = ids['bob']

    # ban bob by alice
    asyncio.run(admin_service.ban_user(alice, bob))

    async def check_ban():
        async with aiosqlite.connect(db_path) as conn:
            cur = await conn.execute('SELECT banned_id FROM bans WHERE banned_id = ?', (bob,))
            row = await cur.fetchone()
            return row[0] if row else None

    found = asyncio.run(check_ban())
    assert found == bob

    # unban
    asyncio.run(admin_service.unban_user(bob))
    async def check_unban():
        async with aiosqlite.connect(db_path) as conn:
            cur = await conn.execute('SELECT banned_id FROM bans WHERE banned_id = ?', (bob,))
            row = await cur.fetchone()
            return row
    assert asyncio.run(check_unban()) is None


def test_delete_user_and_cleanup(tmp_path):
    db_path = setup_temp_db(tmp_path)
    insert_users(db_path)
    ids = get_user_ids(db_path)
    alice = ids['alice']
    bob = ids['bob']

    # create related rows referencing alice
    async def populate():
        async with aiosqlite.connect(db_path) as conn:
            # sessions
            await conn.execute('INSERT INTO sessions (jti, user_id, created_at, expires_at) VALUES (?, ?, ?, ?)', ('j1', alice, 1, 999999))
            # tab_presence
            await conn.execute('INSERT INTO tab_presence (tab_id, jti, user_id, created_at, last_active) VALUES (?, ?, ?, ?, ?)', ('t1', 'j1', alice, 1, 1))
            # friends
            await conn.execute('INSERT INTO friends (user_id, friend_id, created_at) VALUES (?, ?, ?)', (alice, bob, 1))
            # friend_requests
            await conn.execute('INSERT INTO friend_requests (from_id, to_id, message, status, created_at) VALUES (?, ?, ?, ?, ?)', (alice, bob, 'hi', 'pending', 1))
            # messages
            await conn.execute('INSERT INTO messages (room_id, user_id, text, created_at) VALUES (?, ?, ?, ?)', (1, alice, 'hello', 1))
            # message_files referencing message id 1
            await conn.execute('INSERT INTO message_files (message_id, room_file_id, created_at) VALUES (?, ?, ?)', (1, 1, 1))
            # private messages and private_message_files
            await conn.execute('INSERT INTO private_messages (from_id, to_id, text, created_at) VALUES (?, ?, ?, ?)', (alice, bob, 'pm', 1))
            await conn.execute('INSERT INTO private_message_files (message_id, from_id, to_id, path, created_at) VALUES (?, ?, ?, ?, ?)', (1, alice, bob, '/tmp/f', 1))
            # bans
            await conn.execute('INSERT INTO bans (banner_id, banned_id, created_at) VALUES (?, ?, ?)', (bob, alice, 1))
            await conn.commit()
    asyncio.run(populate())

    # delete alice
    from services import admin_service
    asyncio.run(admin_service.delete_user_and_cleanup(alice))

    # verify users row removed and related rows cleaned
    async def verify():
        async with aiosqlite.connect(db_path) as conn:
            cur = await conn.execute('SELECT id FROM users WHERE id = ?', (alice,))
            u = await cur.fetchone()
            cur = await conn.execute('SELECT jti FROM sessions WHERE user_id = ?', (alice,))
            s = await cur.fetchone()
            cur = await conn.execute('SELECT id FROM friends WHERE user_id = ? OR friend_id = ?', (alice, alice))
            f = await cur.fetchone()
            cur = await conn.execute('SELECT id FROM friend_requests WHERE from_id = ? OR to_id = ?', (alice, alice))
            fr = await cur.fetchone()
            cur = await conn.execute('SELECT id FROM messages WHERE user_id = ?', (alice,))
            m = await cur.fetchone()
            cur = await conn.execute('SELECT id FROM bans WHERE banned_id = ? OR banner_id = ?', (alice, alice))
            b = await cur.fetchone()
            return u, s, f, fr, m, b

    u, s, f, fr, m, b = asyncio.run(verify())
    assert u is None
    assert s is None
    assert f is None
    assert fr is None
    assert m is None
    assert b is None


def test_parse_pagination_helper():
    # import helper directly
    from routers.admin import _parse_pagination

    class Dummy:
        def __init__(self, q):
            self.query_params = q

    # basic parse
    page, per_page, offset = _parse_pagination(Dummy({'page': '2', 'per_page': '10'}))
    assert page == 2 and per_page == 10 and offset == 10

    # defaults
    page, per_page, offset = _parse_pagination(Dummy({}))
    assert page == 1 and per_page == 50 and offset == 0
