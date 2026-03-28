import uuid
import os


def _reg_and_token(client, prefix='user'):
    suffix = str(uuid.uuid4())[:8]
    email = f'{prefix}_{suffix}@example.com'
    username = f'{prefix}_{suffix}'
    r = client.post('/register', json={'email': email, 'username': username, 'password': 'pass'})
    assert r.status_code == 200
    return r.json()['user'], r.json()['token']


def test_room_deletion_removes_messages_and_files(client):
    owner, owner_token = _reg_and_token(client, 'owner')
    client.s.headers.update({'Authorization': f'Bearer {owner_token}'})
    # create a public room
    rn = f"deleteroom_{str(uuid.uuid4())[:8]}"
    r = client.post('/rooms', json={'name': rn})
    assert r.status_code == 200
    rid = r.json()['room']['id']

    # post a message
    client.s.headers.update({'Authorization': f'Bearer {owner_token}'})
    pm = client.post(f'/rooms/{rid}/messages', json={'text': 'hello'})
    assert pm.status_code == 200

    # create uploads dir and dummy file
    os.makedirs('uploads', exist_ok=True)
    fname = f'testfile_{rid}.dat'
    fpath = os.path.join('uploads', fname)
    with open(fpath, 'wb') as fh:
        fh.write(b'hello')

    # record file in DB
    # use sqlite via a small helper endpoint: we will insert via rooms.members/add? No direct endpoint
    # so insert by using the DB directly from the test process
    import sqlite3

    from core.config import DB_PATH
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute('INSERT INTO room_files (room_id, path, created_at) VALUES (?, ?, ?)', (rid, fname, 1))
    conn.commit()
    conn.close()

    # delete the room as owner
    client.s.headers.update({'Authorization': f'Bearer {owner_token}'})
    dr = client.s.delete(client.s.base_url + f'/rooms/{rid}')
    assert dr.status_code == 200

    # file should be deleted
    assert not os.path.exists(fpath)

    # DB rows for messages and files should be gone
    from core.config import DB_PATH
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute('SELECT COUNT(*) FROM messages WHERE room_id = ?', (rid,))
    assert cur.fetchone()[0] == 0
    cur.execute('SELECT COUNT(*) FROM room_files WHERE room_id = ?', (rid,))
    assert cur.fetchone()[0] == 0
    conn.close()
