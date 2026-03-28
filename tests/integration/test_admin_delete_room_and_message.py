import uuid
import sqlite3
import requests
import time
import os
import pytest
from test_auth_admin import BASE, unique_email, server_available


@pytest.mark.skipif(not server_available(), reason="server not running on localhost:8000")
def test_admin_delete_room_cascades():
    # create admin
    admin_email = unique_email(); admin_username = 'adm-' + uuid.uuid4().hex[:8]; pw = 'adminpw'
    r = requests.post(BASE + '/register', json={'email': admin_email, 'username': admin_username, 'password': pw})
    assert r.status_code == 200
    admin_token = r.json().get('token'); admin_user = r.json().get('user')
    # promote to admin in DB
    from core.config import DB_PATH
    conn = sqlite3.connect(DB_PATH); cur = conn.cursor(); cur.execute('UPDATE users SET is_admin = 1 WHERE id = ?', (admin_user['id'],)); conn.commit(); conn.close()

    # create an owner user and a room
    owner_email = unique_email(); owner_username = 'own-' + uuid.uuid4().hex[:8]; pw = 'pw'
    r = requests.post(BASE + '/register', json={'email': owner_email, 'username': owner_username, 'password': pw})
    assert r.status_code == 200
    owner_token = r.json().get('token'); owner = r.json().get('user')

    # create room as owner
    headers = {'Authorization': f'Bearer {owner_token}'}
    rn = f"admdeleteroom_{uuid.uuid4().hex[:6]}"
    r = requests.post(BASE + '/rooms', headers=headers, json={'name': rn})
    assert r.status_code == 200
    rid = r.json()['room']['id']

    # post a message as owner
    r = requests.post(f'{BASE}/rooms/{rid}/messages', headers=headers, json={'text': 'to be deleted in room'})
    assert r.status_code == 200
    mid = r.json()['message']['id']

    # create a dummy room file on disk and register it in DB
    os.makedirs('uploads', exist_ok=True)
    fname = f'testfile_room_{rid}.dat'
    fpath = os.path.join('uploads', fname)
    with open(fpath, 'wb') as fh: fh.write(b'zzz')
    from core.config import DB_PATH
    conn = sqlite3.connect(DB_PATH); cur = conn.cursor()
    cur.execute('INSERT INTO room_files (room_id, path, created_at) VALUES (?, ?, ?)', (rid, fname, int(time.time())))
    rfid = cur.lastrowid
    # link message_files to the message
    cur.execute('INSERT INTO message_files (message_id, room_file_id, created_at) VALUES (?, ?, ?)', (mid, rfid, int(time.time())))
    # add a membership and room_admin entry for owner to verify removal
    cur.execute('INSERT OR IGNORE INTO memberships (room_id, user_id, created_at) VALUES (?, ?, ?)', (rid, owner['id'], int(time.time())))
    cur.execute('INSERT OR IGNORE INTO room_admins (room_id, user_id, created_at) VALUES (?, ?, ?)', (rid, owner['id'], int(time.time())))
    conn.commit(); conn.close()

    # now call admin delete room
    r = requests.post(BASE + '/admin/delete_room', headers={'Authorization': f'Bearer {admin_token}'}, json={'room_id': rid})
    assert r.status_code == 200 and r.json().get('ok') is True

    # DB checks
    from core.config import DB_PATH
    conn = sqlite3.connect(DB_PATH); cur = conn.cursor()
    cur.execute('SELECT id FROM rooms WHERE id = ?', (rid,)); assert cur.fetchone() is None
    cur.execute('SELECT COUNT(*) FROM messages WHERE room_id = ?', (rid,)); assert cur.fetchone()[0] == 0
    cur.execute('SELECT COUNT(*) FROM room_files WHERE room_id = ?', (rid,)); assert cur.fetchone()[0] == 0
    cur.execute('SELECT COUNT(*) FROM message_files WHERE message_id = ?', (mid,)); assert cur.fetchone()[0] == 0
    cur.execute('SELECT COUNT(*) FROM memberships WHERE room_id = ?', (rid,)); assert cur.fetchone()[0] == 0
    cur.execute('SELECT COUNT(*) FROM room_admins WHERE room_id = ?', (rid,)); assert cur.fetchone()[0] == 0
    cur.execute('SELECT COUNT(*) FROM invitations WHERE room_id = ?', (rid,)); assert cur.fetchone()[0] == 0
    conn.close()


@pytest.mark.skipif(not server_available(), reason="server not running on localhost:8000")
def test_admin_delete_message_cascades():
    # create admin and promote
    admin_email = unique_email(); admin_username = 'admmsg-' + uuid.uuid4().hex[:8]; pw = 'adminpw'
    r = requests.post(BASE + '/register', json={'email': admin_email, 'username': admin_username, 'password': pw})
    assert r.status_code == 200
    admin_token = r.json().get('token'); admin_user = r.json().get('user')
    conn = sqlite3.connect('auth.db'); cur = conn.cursor(); cur.execute('UPDATE users SET is_admin = 1 WHERE id = ?', (admin_user['id'],)); conn.commit(); conn.close()

    # create owner and room and message
    owner_email = unique_email(); owner_username = 'ownmsg-' + uuid.uuid4().hex[:8]
    r = requests.post(BASE + '/register', json={'email': owner_email, 'username': owner_username, 'password': 'pw'})
    assert r.status_code == 200
    owner_token = r.json().get('token'); owner = r.json().get('user')
    headers = {'Authorization': f'Bearer {owner_token}'}
    r = requests.post(BASE + '/rooms', headers=headers, json={'name': f'msgroom_{uuid.uuid4().hex[:6]}'})
    assert r.status_code == 200
    rid = r.json()['room']['id']
    r = requests.post(f'{BASE}/rooms/{rid}/messages', headers=headers, json={'text': 'admin delete me'})
    assert r.status_code == 200
    mid = r.json()['message']['id']

    # create a room_file and message_files linking it
    conn = sqlite3.connect('auth.db'); cur = conn.cursor()
    cur.execute('INSERT INTO room_files (room_id, path, created_at) VALUES (?, ?, ?)', (rid, f'msgfile_{mid}.dat', int(time.time())))
    rfid = cur.lastrowid
    cur.execute('INSERT INTO message_files (message_id, room_file_id, created_at) VALUES (?, ?, ?)', (mid, rfid, int(time.time())))
    conn.commit(); conn.close()

    # admin deletes the message
    r = requests.post(BASE + '/admin/delete_message', headers={'Authorization': f'Bearer {admin_token}'}, json={'message_id': mid})
    assert r.status_code == 200 and r.json().get('ok') is True

    # DB checks: message gone, message_files gone, and room_files removed
    conn = sqlite3.connect('auth.db'); cur = conn.cursor()
    cur.execute('SELECT id FROM messages WHERE id = ?', (mid,)); assert cur.fetchone() is None
    cur.execute('SELECT COUNT(*) FROM message_files WHERE message_id = ?', (mid,)); assert cur.fetchone()[0] == 0
    cur.execute('SELECT COUNT(*) FROM room_files WHERE id = ?', (rfid,)); assert cur.fetchone()[0] == 0
    conn.close()
