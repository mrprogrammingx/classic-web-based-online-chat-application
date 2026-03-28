import uuid
import sqlite3
import requests
import time
import pytest
from test_auth_admin import BASE, unique_email, server_available


@pytest.mark.skipif(not server_available(), reason="server not running on localhost:8000")
def test_delete_user_cascades_related_records():
    # create admin
    admin_email = unique_email(); admin_username = 'adm-' + uuid.uuid4().hex[:8]; pw = 'adminpw'
    r = requests.post(BASE + '/register', json={'email': admin_email, 'username': admin_username, 'password': pw})
    assert r.status_code == 200
    admin_token = r.json().get('token'); admin_user = r.json().get('user')
    # make admin in DB
    from core.config import DB_PATH
    conn = sqlite3.connect(DB_PATH); cur = conn.cursor(); cur.execute('UPDATE users SET is_admin = 1 WHERE id = ?', (admin_user['id'],)); conn.commit(); conn.close()

    # create target user
    target_email = unique_email(); target_username = 'tgt-' + uuid.uuid4().hex[:8]
    r = requests.post(BASE + '/register', json={'email': target_email, 'username': target_username, 'password': 'pw'})
    assert r.status_code == 200
    target = r.json().get('user')

    # create side-effects directly in DB: ban, friend, session, membership, message, dialog read
    from core.config import DB_PATH
    conn = sqlite3.connect(DB_PATH); cur = conn.cursor()
    # ban: admin bans target
    cur.execute('INSERT OR IGNORE INTO bans (banner_id, banned_id, created_at) VALUES (?, ?, ?)', (admin_user['id'], target['id'], int(time.time())))
    # session
    cur.execute('INSERT OR IGNORE INTO sessions (jti, user_id, created_at, expires_at) VALUES (?, ?, ?, ?)', ('jti-'+uuid.uuid4().hex[:6], target['id'], int(time.time()), int(time.time())+3600))
    # membership: create a room and membership
    cur.execute('INSERT INTO rooms (owner_id, name, created_at) VALUES (?, ?, ?)', (admin_user['id'], 'room-for-delete-'+uuid.uuid4().hex[:6], int(time.time())))
    room_id = cur.lastrowid
    cur.execute('INSERT INTO memberships (room_id, user_id, created_at) VALUES (?, ?, ?)', (room_id, target['id'], int(time.time())))
    # room_admins
    cur.execute('INSERT INTO room_admins (room_id, user_id, created_at) VALUES (?, ?, ?)', (room_id, target['id'], int(time.time())))
    # message authored by target
    cur.execute('INSERT INTO messages (room_id, user_id, text, created_at) VALUES (?, ?, ?, ?)', (room_id, target['id'], 'hello', int(time.time())))
    msg_id = cur.lastrowid
    # message_files referencing that message
    cur.execute('INSERT INTO message_files (message_id, room_file_id, created_at) VALUES (?, ?, ?)', (msg_id, 0, int(time.time())))
    # friend relation
    cur.execute('INSERT INTO friends (user_id, friend_id, created_at) VALUES (?, ?, ?)', (target['id'], admin_user['id'], int(time.time())))
    # friend request
    cur.execute('INSERT INTO friend_requests (from_id, to_id, message, status, created_at) VALUES (?, ?, ?, ?, ?)', (target['id'], admin_user['id'], 'pls', 'pending', int(time.time())))
    # dialog_reads
    cur.execute('INSERT INTO dialog_reads (user_id, other_id, last_read_at) VALUES (?, ?, ?)', (target['id'], admin_user['id'], int(time.time())))
    conn.commit(); conn.close()

    # now delete target via admin API
    r = requests.post(BASE + '/admin/users/delete', headers={'Authorization': f'Bearer {admin_token}'}, json={'id': target['id']})
    assert r.status_code == 200 and r.json().get('ok') is True

    # check DB that related rows are gone
    from core.config import DB_PATH
    conn = sqlite3.connect(DB_PATH); cur = conn.cursor()
    cur.execute('SELECT id FROM users WHERE id = ?', (target['id'],)); assert cur.fetchone() is None
    cur.execute('SELECT id FROM bans WHERE banned_id = ?', (target['id'],)); assert cur.fetchone() is None
    cur.execute('SELECT jti FROM sessions WHERE user_id = ?', (target['id'],)); assert cur.fetchone() is None
    cur.execute('SELECT id FROM memberships WHERE user_id = ?', (target['id'],)); assert cur.fetchone() is None
    cur.execute('SELECT id FROM room_admins WHERE user_id = ?', (target['id'],)); assert cur.fetchone() is None
    cur.execute('SELECT id FROM messages WHERE user_id = ?', (target['id'],)); assert cur.fetchone() is None
    cur.execute('SELECT id FROM message_files WHERE message_id = ?', (msg_id,)); assert cur.fetchone() is None
    cur.execute('SELECT id FROM friends WHERE user_id = ? OR friend_id = ?', (target['id'], target['id'])); assert cur.fetchone() is None
    cur.execute('SELECT id FROM friend_requests WHERE from_id = ? OR to_id = ?', (target['id'], target['id'])); assert cur.fetchone() is None
    cur.execute('SELECT id FROM dialog_reads WHERE user_id = ? OR other_id = ?', (target['id'], target['id'])); assert cur.fetchone() is None
    conn.close()


@pytest.mark.skipif(not server_available(), reason="server not running on localhost:8000")
def test_admin_users_and_banned_list_consistency():
    # create admin
    admin_email = unique_email(); admin_username = 'adm2-' + uuid.uuid4().hex[:8]; pw = 'adminpw'
    r = requests.post(BASE + '/register', json={'email': admin_email, 'username': admin_username, 'password': pw})
    assert r.status_code == 200
    admin_token = r.json().get('token'); admin_user = r.json().get('user')
    conn = sqlite3.connect('auth.db'); cur = conn.cursor(); cur.execute('UPDATE users SET is_admin = 1 WHERE id = ?', (admin_user['id'],)); conn.commit(); conn.close()

    # create three users: one admin, one banned, one normal
    u1 = requests.post(BASE + '/register', json={'email': unique_email(), 'username': 'u1-'+uuid.uuid4().hex[:6], 'password': 'pw'}).json().get('user')
    u2 = requests.post(BASE + '/register', json={'email': unique_email(), 'username': 'u2-'+uuid.uuid4().hex[:6], 'password': 'pw'}).json().get('user')
    u3 = requests.post(BASE + '/register', json={'email': unique_email(), 'username': 'u3-'+uuid.uuid4().hex[:6], 'password': 'pw'}).json().get('user')
    # make u1 admin
    r = requests.post(BASE + '/admin/make_admin', headers={'Authorization': f'Bearer {admin_token}'}, json={'user_id': u1['id']}); assert r.status_code == 200
    # ban u2
    r = requests.post(BASE + '/admin/ban_user', headers={'Authorization': f'Bearer {admin_token}'}, json={'user_id': u2['id']}); assert r.status_code == 200

    # fetch /admin/users and /admin/banned
    r1 = requests.get(BASE + '/admin/users', headers={'Authorization': f'Bearer {admin_token}'}); assert r1.status_code == 200
    us = r1.json().get('users')
    ids = {u['id'] for u in us}
    assert u1['id'] in ids and u2['id'] in ids and u3['id'] in ids
    # check admin flag present for u1
    byid = {u['id']: u for u in us}
    assert byid[u1['id']]['is_admin'] is True

    r2 = requests.get(BASE + '/admin/banned', headers={'Authorization': f'Bearer {admin_token}'}); assert r2.status_code == 200
    banned = r2.json().get('banned')
    banned_ids = {b['banned_id'] for b in banned}
    assert u2['id'] in banned_ids and u1['id'] not in banned_ids
