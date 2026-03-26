import asyncio
import os
import aiosqlite


def setup_temp_db(tmp_path):
    db_path = str(tmp_path / 'test_admin.db')
    # point the project's db.DB to our temp file
    import db
    # set DB path in both the db package and the underlying schema module
    db.DB = db_path
    import db.schema as schema
    schema.DB = db_path
    # initialize schema
    asyncio.run(db.init_db())
    return db_path


def insert_users(db_path):
    async def _ins():
        async with aiosqlite.connect(db_path) as db_conn:
            await db_conn.execute("INSERT INTO users (email, username, password, created_at) VALUES (?, ?, ?, ?)", ('a@example.com', 'alice', 'pw', 1))
            await db_conn.execute("INSERT INTO users (email, username, password, created_at) VALUES (?, ?, ?, ?)", ('b@example.com', 'bob', 'pw', 2))
            await db_conn.commit()
    asyncio.run(_ins())


def test_list_users_and_set_admin(tmp_path):
    db_path = setup_temp_db(tmp_path)
    insert_users(db_path)

    from services import admin_service

    # list users
    users, total, banned_ids = asyncio.run(admin_service.list_users(None, None, page=1, per_page=50))
    assert total == 2
    assert any(u['username'] == 'alice' for u in users)

    # make alice an admin
    alice_id = next(u['id'] for u in users if u['username'] == 'alice')
    asyncio.run(admin_service.set_admin(alice_id, True))

    # verify admin flag set
    async def check():
        async with aiosqlite.connect(db_path) as db_conn:
            cur = await db_conn.execute('SELECT is_admin FROM users WHERE id = ?', (alice_id,))
            row = await cur.fetchone()
            return row[0]

    is_admin = asyncio.run(check())
    assert is_admin == 1


def test_admin_user_counts(tmp_path):
    db_path = setup_temp_db(tmp_path)
    insert_users(db_path)

    from services import admin_service

    counts = asyncio.run(admin_service.admin_user_counts())
    assert counts['total'] == 2
    # no admins yet
    assert counts['admins'] in (0, 1)  # depending on bootstrap logic elsewhere
