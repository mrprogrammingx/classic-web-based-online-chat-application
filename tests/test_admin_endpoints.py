import uuid
import sqlite3
import requests
import pytest
from test_auth_admin import BASE, unique_email, server_available


@pytest.mark.skipif(not server_available(), reason="server not running on localhost:8000")
def test_ban_and_unban_user():
    # create admin
    admin_email = unique_email()
    admin_username = 'admin-' + uuid.uuid4().hex[:8]
    pw = 'adminpass'
    r = requests.post(BASE + '/register', json={'email': admin_email, 'username': admin_username, 'password': pw})
    assert r.status_code == 200
    admin_token = r.json().get('token')
    admin_user = r.json().get('user')

    # promote to admin in DB
    conn = sqlite3.connect('auth.db')
    cur = conn.cursor()
    cur.execute('UPDATE users SET is_admin = 1 WHERE id = ?', (admin_user['id'],))
    conn.commit(); conn.close()

    # create target user
    target_email = unique_email()
    target_username = 'target-' + uuid.uuid4().hex[:8]
    r = requests.post(BASE + '/register', json={'email': target_email, 'username': target_username, 'password': 'pw'})
    assert r.status_code == 200
    target_user = r.json().get('user')

    # ban via admin API
    r = requests.post(BASE + '/admin/ban_user', headers={'Authorization': f'Bearer {admin_token}'}, json={'user_id': target_user['id']})
    assert r.status_code == 200 and r.json().get('ok') is True

    # check DB for ban
    conn = sqlite3.connect('auth.db')
    cur = conn.cursor(); cur.execute('SELECT banned_id FROM bans WHERE banned_id = ?', (target_user['id'],)); row = cur.fetchone(); conn.close()
    assert row is not None and row[0] == target_user['id']

    # unban
    r = requests.post(BASE + '/admin/unban_user', headers={'Authorization': f'Bearer {admin_token}'}, json={'user_id': target_user['id']})
    assert r.status_code == 200 and r.json().get('ok') is True
    conn = sqlite3.connect('auth.db'); cur = conn.cursor(); cur.execute('SELECT banned_id FROM bans WHERE banned_id = ?', (target_user['id'],)); row = cur.fetchone(); conn.close()
    assert row is None


@pytest.mark.skipif(not server_available(), reason="server not running on localhost:8000")
def test_make_and_revoke_admin():
    admin_email = unique_email()
    admin_username = 'admin2-' + uuid.uuid4().hex[:8]
    pw = 'adminpass'
    r = requests.post(BASE + '/register', json={'email': admin_email, 'username': admin_username, 'password': pw})
    assert r.status_code == 200
    admin_token = r.json().get('token')
    admin_user = r.json().get('user')
    conn = sqlite3.connect('auth.db'); cur = conn.cursor(); cur.execute('UPDATE users SET is_admin = 1 WHERE id = ?', (admin_user['id'],)); conn.commit(); conn.close()

    # create target
    target_email = unique_email(); target_username = 'target2-' + uuid.uuid4().hex[:8]
    r = requests.post(BASE + '/register', json={'email': target_email, 'username': target_username, 'password': 'pw'})
    assert r.status_code == 200
    target_user = r.json().get('user')

    # make admin
    r = requests.post(BASE + '/admin/make_admin', headers={'Authorization': f'Bearer {admin_token}'}, json={'user_id': target_user['id']})
    assert r.status_code == 200 and r.json().get('ok') is True
    conn = sqlite3.connect('auth.db'); cur = conn.cursor(); cur.execute('SELECT is_admin FROM users WHERE id = ?', (target_user['id'],)); row = cur.fetchone(); conn.close()
    assert row is not None and row[0] == 1

    # revoke
    r = requests.post(BASE + '/admin/revoke_admin', headers={'Authorization': f'Bearer {admin_token}'}, json={'user_id': target_user['id']})
    assert r.status_code == 200 and r.json().get('ok') is True
    conn = sqlite3.connect('auth.db'); cur = conn.cursor(); cur.execute('SELECT is_admin FROM users WHERE id = ?', (target_user['id'],)); row = cur.fetchone(); conn.close()
    assert row is not None and row[0] == 0


@pytest.mark.skipif(not server_available(), reason="server not running on localhost:8000")
def test_delete_room():
    # create admin
    admin_email = unique_email(); admin_username = 'admin3-' + uuid.uuid4().hex[:8]; pw = 'adminpass'
    r = requests.post(BASE + '/register', json={'email': admin_email, 'username': admin_username, 'password': pw})
    assert r.status_code == 200
    admin_token = r.json().get('token'); admin_user = r.json().get('user')
    conn = sqlite3.connect('auth.db'); cur = conn.cursor(); cur.execute('UPDATE users SET is_admin = 1 WHERE id = ?', (admin_user['id'],)); conn.commit(); conn.close()

    # create room
    r = requests.post(BASE + '/rooms', headers={'Authorization': f'Bearer {admin_token}'}, json={'name': 'test-room-' + uuid.uuid4().hex[:6]})
    assert r.status_code == 200
    room = r.json().get('room')

    # delete room
    r = requests.post(BASE + '/admin/delete_room', headers={'Authorization': f'Bearer {admin_token}'}, json={'room_id': room['id']})
    assert r.status_code == 200 and r.json().get('ok') is True
    # verify room gone
    conn = sqlite3.connect('auth.db'); cur = conn.cursor(); cur.execute('SELECT id FROM rooms WHERE id = ?', (room['id'],)); row = cur.fetchone(); conn.close()
    assert row is None
