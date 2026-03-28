import uuid
import sqlite3
import requests
import pytest
from test_auth_admin import BASE, unique_email, server_available


@pytest.mark.skipif(not server_available(), reason="server not running on localhost:8000")
def test_banned_pagination():
    admin_email = unique_email()
    admin_username = 'adm-ban-' + uuid.uuid4().hex[:6]
    pw = 'adminpw'
    r = requests.post(BASE + '/register', json={'email': admin_email, 'username': admin_username, 'password': pw})
    assert r.status_code == 200
    admin_token = r.json().get('token'); admin_user = r.json().get('user')
    from core.config import DB_PATH
    conn = sqlite3.connect(DB_PATH); cur = conn.cursor(); cur.execute('UPDATE users SET is_admin = 1 WHERE id = ?', (admin_user['id'],)); conn.commit(); conn.close()

    # create and ban 12 users
    created = []
    for i in range(12):
        u = requests.post(BASE + '/register', json={'email': unique_email(), 'username': f'banuser{i}-{uuid.uuid4().hex[:6]}', 'password': 'pw'})
        assert u.status_code == 200
        user = u.json().get('user')
        created.append(user)
        b = requests.post(BASE + '/admin/ban_user', headers={'Authorization': f'Bearer {admin_token}'}, json={'user_id': user['id']})
        assert b.status_code == 200 and b.json().get('ok') is True

    # request page 2 with per_page=5
    r = requests.get(BASE + '/admin/banned?per_page=5&page=2', headers={'Authorization': f'Bearer {admin_token}'})
    assert r.status_code == 200
    body = r.json()
    assert body.get('page') == 2
    assert body.get('per_page') == 5
    assert 'banned' in body and isinstance(body['banned'], list)
    assert len(body['banned']) <= 5
    assert body.get('total', 0) >= 12
