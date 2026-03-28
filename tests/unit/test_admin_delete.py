import asyncio
import aiosqlite


def setup_temp_db(tmp_path):
    db_path = str(tmp_path / 'test_admin_delete.db')
    import db
    db.DB = db_path
    import db.schema as schema
    schema.DB = db_path
    asyncio.run(db.init_db())
    return db_path


def insert_room_with_messages(db_path):
    async def _ins():
        async with aiosqlite.connect(db_path) as conn:
            # create two users
            await conn.execute("INSERT INTO users (email, username, password, created_at) VALUES (?, ?, ?, ?)", ('a@example.com', 'alice', 'pw', 1))
            await conn.execute("INSERT INTO users (email, username, password, created_at) VALUES (?, ?, ?, ?)", ('b@example.com', 'bob', 'pw', 2))
            # create room
            await conn.execute("INSERT INTO rooms (owner_id, name, created_at) VALUES (?, ?, ?)", (1, 'room1', 10))
            # message in room
            await conn.execute("INSERT INTO messages (room_id, user_id, text, created_at) VALUES (?, ?, ?, ?)", (1, 1, 'hello', 11))
            await conn.execute("INSERT INTO message_files (message_id, room_file_id, created_at) VALUES (?, ?, ?)", (1, 1, 12))
            # room file referenced
            await conn.execute("INSERT INTO room_files (room_id, path, created_at) VALUES (?, ?, ?)", (1, '/tmp/f', 13))
            # membership
            await conn.execute("INSERT INTO memberships (room_id, user_id, created_at) VALUES (?, ?, ?)", (1, 1, 14))
            # room_admins
            await conn.execute("INSERT INTO room_admins (room_id, user_id, created_at) VALUES (?, ?, ?)", (1, 1, 15))
            # room_bans
            await conn.execute("INSERT INTO room_bans (room_id, banned_id, banner_id, created_at) VALUES (?, ?, ?, ?)", (1, 2, 1, 16))
            # invitations
            await conn.execute("INSERT INTO invitations (room_id, inviter_id, invitee_id, created_at) VALUES (?, ?, ?, ?)", (1, 1, 2, 17))
            await conn.commit()
    asyncio.run(_ins())


def insert_private_and_room_message(db_path):
    async def _ins():
        async with aiosqlite.connect(db_path) as conn:
            # create users
            await conn.execute("INSERT INTO users (email, username, password, created_at) VALUES (?, ?, ?, ?)", ('c@example.com', 'carol', 'pw', 1))
            await conn.execute("INSERT INTO users (email, username, password, created_at) VALUES (?, ?, ?, ?)", ('d@example.com', 'dave', 'pw', 2))
            # private message and private file
            cur = await conn.execute("INSERT INTO private_messages (from_id, to_id, text, created_at) VALUES (?, ?, ?, ?)", (1, 2, 'hi', 20))
            pm_id = cur.lastrowid
            await conn.execute("INSERT INTO private_message_files (message_id, from_id, to_id, path, created_at) VALUES (?, ?, ?, ?, ?)", (pm_id, 1, 2, '/tmp/f2', 21))
            # room message with file linking to room_files
            cur = await conn.execute("INSERT INTO rooms (owner_id, name, created_at) VALUES (?, ?, ?)", (1, 'r2', 30))
            room_id = cur.lastrowid
            cur = await conn.execute("INSERT INTO messages (room_id, user_id, text, created_at) VALUES (?, ?, ?, ?)", (room_id, 1, 'rm', 31))
            msg_id = cur.lastrowid
            cur = await conn.execute("INSERT INTO room_files (room_id, path, created_at) VALUES (?, ?, ?)", (room_id, '/tmp/rf', 32))
            rf_id = cur.lastrowid
            await conn.execute("INSERT INTO message_files (message_id, room_file_id, created_at) VALUES (?, ?, ?)", (msg_id, rf_id, 33))
            await conn.commit()
            cur = await conn.execute('SELECT id FROM messages ORDER BY id DESC LIMIT 1')
            mrow = await cur.fetchone()
            cur = await conn.execute('SELECT id FROM private_messages ORDER BY id DESC LIMIT 1')
            prow = await cur.fetchone()
            return (mrow[0] if mrow else None), (prow[0] if prow else None)
    return asyncio.run(_ins())


def test_delete_room_and_cleanup(tmp_path):
    db_path = setup_temp_db(tmp_path)
    insert_room_with_messages(db_path)

    from services import admin_service

    res = asyncio.run(admin_service.delete_room_and_cleanup(1))
    # expect the room and its related items to be reported
    assert res['room'] == 1
    assert res['messages'] == 1
    assert res['message_files'] == 1
    assert res['room_files'] == 1
    assert res['memberships'] == 1
    assert res['room_admins'] == 1
    assert res['room_bans'] == 1
    assert res['invitations'] == 1


def test_delete_message_and_cleanup(tmp_path):
    db_path = setup_temp_db(tmp_path)
    room_msg_id, private_msg_id = insert_private_and_room_message(db_path)

    from services import admin_service
    assert room_msg_id is not None
    assert private_msg_id is not None

    # delete private message first
    res2 = asyncio.run(admin_service.delete_message_and_cleanup(private_msg_id))

    # now delete the room message
    res = asyncio.run(admin_service.delete_message_and_cleanup(room_msg_id))

    # ids may collide between tables (private and room messages can share the same numeric id).
    # Ensure cumulative deletions equal what we inserted: 2 messages total (1 private + 1 room),
    # 2 message_files (one for private as private_message_files and one for room message), and 1 room_file.
    total_messages_deleted = (res.get('messages', 0) + res.get('private_messages', 0) +
                              res2.get('messages', 0) + res2.get('private_messages', 0))
    total_message_files_deleted = (res.get('message_files', 0) + res.get('private_message_files', 0) +
                                   res2.get('message_files', 0) + res2.get('private_message_files', 0))
    total_room_files_deleted = (res.get('room_files', 0) + res2.get('room_files', 0))

    assert total_messages_deleted == 2
    assert total_message_files_deleted == 2
    assert total_room_files_deleted == 1
