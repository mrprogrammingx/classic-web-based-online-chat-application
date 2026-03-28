import uuid
import sqlite3
import requests
import pytest
from test_auth_admin import BASE, unique_email, server_available


@pytest.mark.skipif(not server_available(), reason="server not running on localhost:8000")
def test_static_admin_js_contains_admins_tab():
    # fetch the admin client JS and check it wires an Admins tab
    r = requests.get(BASE + '/static/admin/admin.js', timeout=5)
    assert r.status_code == 200
    text = r.text
    # ensure the tabs include 'Admins'
    assert "'Users', 'Admins', 'Banned'" in text or 'Admins' in text
    # ensure the admin renderer is imported
    assert 'renderAdminRole' in text


@pytest.mark.skipif(not server_available(), reason="server not running on localhost:8000")
def test_admin_users_filter_admins():
    # create an admin user and promote in DB
    admin_email = unique_email()
    admin_username = 'adm-test-' + uuid.uuid4().hex[:6]
    pw = 'adminpw'
    r = requests.post(BASE + '/register', json={'email': admin_email, 'username': admin_username, 'password': pw})
    assert r.status_code == 200
    admin_token = r.json().get('token'); admin_user = r.json().get('user')
    from core.config import DB_PATH
    conn = sqlite3.connect(DB_PATH); cur = conn.cursor(); cur.execute('UPDATE users SET is_admin = 1 WHERE id = ?', (admin_user['id'],)); conn.commit(); conn.close()

    # create a target user and promote them to admin in DB
    t_email = unique_email()
    t_username = 'target-' + uuid.uuid4().hex[:6]
    tr = requests.post(BASE + '/register', json={'email': t_email, 'username': t_username, 'password': 'pw'})
    assert tr.status_code == 200
    target = tr.json().get('user')
    from core.config import DB_PATH
    conn = sqlite3.connect(DB_PATH); cur = conn.cursor(); cur.execute('UPDATE users SET is_admin = 1 WHERE id = ?', (target['id'],)); conn.commit(); conn.close()

    # request admin users filtered
    h = {'Authorization': f'Bearer {admin_token}'}
    r = requests.get(BASE + '/admin/users?filter=admins&per_page=50&page=1', headers=h)
    assert r.status_code == 200
    body = r.json()
    assert body.get('page') == 1
    assert body.get('per_page') == 50
    users = body.get('users', [])
    assert any(u.get('id') == target['id'] for u in users), 'Promoted admin not found in admins list'
