
import time
import uuid
import pytest
import sqlite3
import requests

BASE = 'http://127.0.0.1:8000'


def unique_email():
    return f"test+{uuid.uuid4().hex}@example.com"


def server_available():
    try:
        r = requests.get(BASE + '/')
        return r.status_code in (200, 307)
    except Exception:
        return False


@pytest.mark.skipif(not server_available(), reason="server not running on localhost:8000")
def test_register_login_and_me():
    email = unique_email()
    username = 'user-' + uuid.uuid4().hex[:8]
    pw = 'pass1234'

    r = requests.post(BASE + '/register', json={'email': email, 'username': username, 'password': pw})
    assert r.status_code == 200
    data = r.json()
    assert 'token' in data
    token = data['token']

    # /me should report is_admin (false for new user)
    r = requests.get(BASE + '/me', headers={'Authorization': f'Bearer {token}'})
    assert r.status_code == 200
    me = r.json().get('user', {})
    assert me.get('email') == email
    assert me.get('username') == username
    assert me.get('is_admin') is False


def promote_user_in_db(user_id: int):
    conn = sqlite3.connect('auth.db')
    cur = conn.cursor()
    cur.execute('UPDATE users SET is_admin = 1 WHERE id = ?', (user_id,))
    conn.commit()
    conn.close()


@pytest.mark.skipif(not server_available(), reason="server not running on localhost:8000")
def test_admin_promote_and_access():
    # create an admin user
    admin_email = unique_email()
    admin_username = 'admin-' + uuid.uuid4().hex[:8]
    pw = 'adminpass'
    r = requests.post(BASE + '/register', json={'email': admin_email, 'username': admin_username, 'password': pw})
    assert r.status_code == 200
    admin_token = r.json().get('token')
    admin_user = r.json().get('user')

    # promote this user to admin in DB
    promote_user_in_db(admin_user['id'])

    # now admin should be able to list users
    r = requests.get(BASE + '/admin/users', headers={'Authorization': f'Bearer {admin_token}'})
    assert r.status_code == 200
    users = r.json().get('users', [])
    assert isinstance(users, list)

    # create a target user to be promoted
    target_email = unique_email()
    target_username = 'target-' + uuid.uuid4().hex[:8]
    r = requests.post(BASE + '/register', json={'email': target_email, 'username': target_username, 'password': 'pw'})
    assert r.status_code == 200
    target_user = r.json().get('user')

    # admin promotes the target via API
    r = requests.post(BASE + '/admin/users/promote', headers={'Authorization': f'Bearer {admin_token}'}, json={'id': target_user['id']})
    assert r.status_code == 200
    assert r.json().get('ok') is True

    # verify in DB that target is now admin
    conn = sqlite3.connect('auth.db')
    cur = conn.cursor()
    cur.execute('SELECT is_admin FROM users WHERE id = ?', (target_user['id'],))
    row = cur.fetchone()
    conn.close()
    assert row is not None and row[0] == 1
