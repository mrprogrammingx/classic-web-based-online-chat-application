import uuid
import sqlite3
import requests
import pytest
from test_auth_admin import BASE, unique_email, server_available


@pytest.mark.skipif(not server_available(), reason="server not running on localhost:8000")
def test_users_counts_and_pagination():
    admin_email = unique_email(); admin_username = 'adm-pg-' + uuid.uuid4().hex[:6]; pw = 'adminpw'
    r = requests.post(BASE + '/register', json={'email': admin_email, 'username': admin_username, 'password': pw})
    assert r.status_code == 200
    admin_token = r.json().get('token'); admin_user = r.json().get('user')
    conn = sqlite3.connect('auth.db'); cur = conn.cursor(); cur.execute('UPDATE users SET is_admin = 1 WHERE id = ?', (admin_user['id'],)); conn.commit(); conn.close()

    # create 25 users for pagination
    created = []
    for i in range(25):
        u = requests.post(BASE + '/register', json={'email': unique_email(), 'username': f'userpg{i}-{uuid.uuid4().hex[:6]}', 'password': 'pw'})
        assert u.status_code == 200
        created.append(u.json().get('user'))

    # counts endpoint
    r = requests.get(BASE + '/admin/users/counts', headers={'Authorization': f'Bearer {admin_token}'})
    assert r.status_code == 200
    data = r.json()
    assert data.get('total', 0) >= 25

    # pagination: per_page=10, page=2 should return items 11-20 (or similar)
    r = requests.get(BASE + '/admin/users?per_page=10&page=2', headers={'Authorization': f'Bearer {admin_token}'})
    assert r.status_code == 200
    body = r.json()
    assert 'users' in body and body.get('page') == 2 and body.get('per_page') == 10
    assert len(body['users']) <= 10


@pytest.mark.skipif(not server_available(), reason="server not running on localhost:8000")
def test_users_search_by_username_and_email():
    admin_email = unique_email(); admin_username = 'adm-sr-' + uuid.uuid4().hex[:6]; pw = 'adminpw'
    r = requests.post(BASE + '/register', json={'email': admin_email, 'username': admin_username, 'password': pw})
    assert r.status_code == 200
    admin_token = r.json().get('token')
    admin_user = r.json().get('user')
    conn = sqlite3.connect('auth.db'); cur = conn.cursor(); cur.execute('UPDATE users SET is_admin = 1 WHERE id = ?', (admin_user['id'],)); conn.commit(); conn.close()

    # create a user with distinctive username/email
    special_username = 'special-user-' + uuid.uuid4().hex[:6]
    special_email = 'special-' + uuid.uuid4().hex[:6] + '@example.test'
    r = requests.post(BASE + '/register', json={'email': special_email, 'username': special_username, 'password': 'pw'})
    assert r.status_code == 200
    u = r.json().get('user')

    # search by username
    r = requests.get(BASE + f'/admin/users?q={special_username}', headers={'Authorization': f'Bearer {admin_token}'})
    assert r.status_code == 200
    res = r.json(); ids = {x['id'] for x in res.get('users', [])}
    assert u['id'] in ids

    # search by email partial
    token = admin_token
    r = requests.get(BASE + f'/admin/users?q={special_email.split("@")[0]}', headers={'Authorization': f'Bearer {token}'})
    assert r.status_code == 200
    res = r.json(); ids = {x['id'] for x in res.get('users', [])}
    assert u['id'] in ids
