import os
import time
import uuid
import sqlite3
from fastapi.testclient import TestClient


def unique_email(prefix='u'):
    return f"{prefix}+{uuid.uuid4().hex[:8]}@example.com"


def test_delete_account_cleans_up_rooms_and_files(tmp_path, monkeypatch):
    # use a temp DB so we don't interfere with other tests
    db_file = tmp_path / 'test_auth.db'
    monkeypatch.setenv('AUTH_DB_PATH', str(db_file))
    # create DB schema
    from db.schema import init_db
    import asyncio
    asyncio.run(init_db())

    # import the app after setting AUTH_DB_PATH so it picks up the test DB
    from routers.app import app
    client = TestClient(app)
    # determine the DB path the app is using (may be different from tmp path if modules cached)
    from db import DB as APP_DB_PATH
    email = unique_email('delroom')
    username = 'u_' + uuid.uuid4().hex[:6]
    pw = 'DeleteRoom123'
    r = client.post('/register', json={'email': email, 'username': username, 'password': pw})
    assert r.status_code == 200
    data = r.json()
    token = data.get('token')
    user = data.get('user')
    assert token and user

    # create a room as this user
    room_name = 'room-' + uuid.uuid4().hex[:6]
    rc = client.post('/rooms', json={'name': room_name, 'description': 'test', 'visibility': 'public'}, headers={'Authorization': f'Bearer {token}'})
    assert rc.status_code == 200
    rid = rc.json()['room']['id']

    # create a dummy file on disk and insert room_files and message referencing it
    uploads_dir = tmp_path / 'uploads'
    uploads_dir.mkdir()
    fname = f'myfile_{uuid.uuid4().hex}.dat'
    fpath = uploads_dir / fname
    with open(fpath, 'wb') as f:
        f.write(b'hello')

    # store relative path in DB (simulate uploader behavior)
    conn = sqlite3.connect(str(APP_DB_PATH))
    try:
        cur = conn.cursor()
        # find user id
        cur.execute('SELECT id FROM users WHERE email = ?', (email,))
        row = cur.fetchone()
        assert row is not None
        uid = row[0]
        # insert room_files record (store basename so deletion logic resolves to uploads/<basename>)
        cur.execute('INSERT INTO room_files (room_id, path, created_at) VALUES (?, ?, ?)', (rid, os.path.basename(str(fpath)), int(time.time())))
        conn.commit()
        # insert a message in the room
        cur.execute('INSERT INTO messages (room_id, user_id, text, created_at) VALUES (?, ?, ?, ?)', (rid, uid, 'hi', int(time.time())))
        mid = cur.lastrowid
        # link message_files -> room_files
        cur.execute('SELECT id FROM room_files WHERE room_id = ?', (rid,))
        rf = cur.fetchone()[0]
        cur.execute('INSERT INTO message_files (message_id, room_file_id, created_at) VALUES (?, ?, ?)', (mid, rf, int(time.time())))
        conn.commit()
    finally:
        conn.close()

    # monkeypatch uploads location resolution: move into project uploads dir so deletion logic finds it
    # copy file into project uploads dir
    proj_uploads = os.path.join(os.getcwd(), 'uploads')
    os.makedirs(proj_uploads, exist_ok=True)
    proj_path = os.path.join(proj_uploads, os.path.basename(str(fpath)))
    with open(fpath, 'rb') as src, open(proj_path, 'wb') as dst:
        dst.write(src.read())

    # now delete account
    rdel = client.delete('/me', headers={'Authorization': f'Bearer {token}'})
    assert rdel.status_code == 200

    # check DB: room should be gone
    conn = sqlite3.connect(str(APP_DB_PATH))
    try:
        cur = conn.cursor()
        cur.execute('SELECT COUNT(*) FROM rooms WHERE id = ?', (rid,))
        assert cur.fetchone()[0] == 0
        cur.execute('SELECT COUNT(*) FROM room_files WHERE room_id = ?', (rid,))
        assert cur.fetchone()[0] == 0
        cur.execute('SELECT COUNT(*) FROM messages WHERE room_id = ?', (rid,))
        assert cur.fetchone()[0] == 0
        cur.execute('SELECT COUNT(*) FROM memberships WHERE user_id = ?', (uid,))
        assert cur.fetchone()[0] == 0
        cur.execute('SELECT id FROM users WHERE email = ?', (email,))
        assert cur.fetchone() is None
    finally:
        conn.close()

    # ensure file removed from project uploads dir
    assert not os.path.exists(proj_path)
