import asyncio
import aiosqlite
import pytest


def setup_temp_db(tmp_path):
    db_path = str(tmp_path / 'test_friends.db')
    import db
    db.DB = db_path
    import db.schema as schema
    schema.DB = db_path
    asyncio.run(db.init_db())
    return db_path


def insert_users(db_path):
    async def _ins():
        async with aiosqlite.connect(db_path) as db_conn:
            await db_conn.execute("INSERT INTO users (email, username, password, created_at) VALUES (?, ?, ?, ?)", ('a@example.com', 'alice', 'pw', 1))
            await db_conn.execute("INSERT INTO users (email, username, password, created_at) VALUES (?, ?, ?, ?)", ('b@example.com', 'bob', 'pw', 2))
            await db_conn.commit()
    asyncio.run(_ins())


def test_friend_request_flow(tmp_path):
    db_path = setup_temp_db(tmp_path)
    insert_users(db_path)

    from services import friends_service

    # fetch user ids
    async def get_ids():
        async with aiosqlite.connect(db_path) as conn:
            cur = await conn.execute('SELECT id, username FROM users ORDER BY id')
            rows = await cur.fetchall()
            return {r[1]: r[0] for r in rows}

    ids = asyncio.run(get_ids())
    alice = ids['alice']
    bob = ids['bob']

    # alice sends friend request to bob
    res = asyncio.run(friends_service.create_friend_request(alice, None, bob, 'hello'))
    assert res == 1

    # bob should see the incoming request
    incoming = asyncio.run(friends_service.list_incoming_requests_for_user(bob))
    assert any(r['from_id'] == alice for r in incoming)

    # bob accepts the request
    rid = incoming[0]['id']
    asyncio.run(friends_service.respond_to_request(bob, rid, 'accept'))

    # now they should be friends (two entries)
    friends_of_alice = asyncio.run(friends_service.list_friends_for_user(alice))
    assert any(f['id'] == bob for f in friends_of_alice)

    # remove friendship
    asyncio.run(friends_service.remove_friend_action(alice, bob))
    friends_of_alice = asyncio.run(friends_service.list_friends_for_user(alice))
    assert not any(f['id'] == bob for f in friends_of_alice)


def test_ban_prevents_request(tmp_path):
    db_path = setup_temp_db(tmp_path)
    insert_users(db_path)

    from services import friends_service

    async def get_ids():
        async with aiosqlite.connect(db_path) as conn:
            cur = await conn.execute('SELECT id, username FROM users ORDER BY id')
            rows = await cur.fetchall()
            return {r[1]: r[0] for r in rows}

    ids = asyncio.run(get_ids())
    alice = ids['alice']
    bob = ids['bob']

    # alice bans bob
    asyncio.run(friends_service.ban_user_action(alice, bob))

    # alice should not be able to send a request to bob (PermissionError)
    try:
        asyncio.run(friends_service.create_friend_request(alice, None, bob, 'hey'))
        assert False, 'expected PermissionError'
    except PermissionError:
        pass


def test_duplicate_request_rejected(tmp_path):
    db_path = setup_temp_db(tmp_path)
    insert_users(db_path)

    from services import friends_service

    async def get_ids():
        async with aiosqlite.connect(db_path) as conn:
            cur = await conn.execute('SELECT id, username FROM users ORDER BY id')
            rows = await cur.fetchall()
            return {r[1]: r[0] for r in rows}

    ids = asyncio.run(get_ids())
    alice = ids['alice']
    bob = ids['bob']

    # first request should succeed
    res = asyncio.run(friends_service.create_friend_request(alice, None, bob, 'hi'))
    assert res == 1

    # second identical request should raise an IntegrityError (duplicate)
    with pytest.raises(Exception):
        asyncio.run(friends_service.create_friend_request(alice, None, bob, 'hi again'))


def test_reject_request(tmp_path):
    db_path = setup_temp_db(tmp_path)
    insert_users(db_path)

    from services import friends_service

    async def get_ids():
        async with aiosqlite.connect(db_path) as conn:
            cur = await conn.execute('SELECT id, username FROM users ORDER BY id')
            rows = await cur.fetchall()
            return {r[1]: r[0] for r in rows}

    ids = asyncio.run(get_ids())
    alice = ids['alice']
    bob = ids['bob']

    # create request
    _ = asyncio.run(friends_service.create_friend_request(alice, None, bob, 'hello'))
    incoming = asyncio.run(friends_service.list_incoming_requests_for_user(bob))
    rid = incoming[0]['id']

    # reject
    asyncio.run(friends_service.respond_to_request(bob, rid, 'reject'))

    # verify status is rejected
    async def check_status():
        async with aiosqlite.connect(db_path) as conn:
            cur = await conn.execute('SELECT status FROM friend_requests WHERE id = ?', (rid,))
            row = await cur.fetchone()
            return row[0]

    status = asyncio.run(check_status())
    assert status == 'rejected'


def test_mutual_ban_check(tmp_path):
    db_path = setup_temp_db(tmp_path)
    insert_users(db_path)

    from services import friends_service

    async def get_ids():
        async with aiosqlite.connect(db_path) as conn:
            cur = await conn.execute('SELECT id, username FROM users ORDER BY id')
            rows = await cur.fetchall()
            return {r[1]: r[0] for r in rows}

    ids = asyncio.run(get_ids())
    alice = ids['alice']
    bob = ids['bob']

    # alice bans bob
    asyncio.run(friends_service.ban_user_action(alice, bob))

    # check ban in either direction
    assert asyncio.run(friends_service.check_ban_for_users(alice, bob)) is True
    assert asyncio.run(friends_service.check_ban_for_users(bob, alice)) is True
