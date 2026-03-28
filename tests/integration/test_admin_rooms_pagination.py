import uuid
import sqlite3
import requests
import pytest
from test_auth_admin import BASE, unique_email, server_available


@pytest.mark.skipif(not server_available(), reason="server not running on localhost:8000")
def test_admin_rooms_pagination_and_search():
    admin_email = unique_email()
    admin_username = 'adm-rooms-' + uuid.uuid4().hex[:6]
    pw = 'adminpw'
    r = requests.post(BASE + '/register', json={'email': admin_email, 'username': admin_username, 'password': pw})
    assert r.status_code == 200
    admin_token = r.json().get('token'); admin_user = r.json().get('user')
    from core.config import DB_PATH
    conn = sqlite3.connect(DB_PATH); cur = conn.cursor(); cur.execute('UPDATE users SET is_admin = 1 WHERE id = ?', (admin_user['id'],)); conn.commit(); conn.close()

    # create 11 rooms, give some distinctive names for search
    room_ids = []
    for i in range(11):
        name = f'room-test-{i}-{uuid.uuid4().hex[:4]}'
        if i == 3:
            name = 'special-search-room-' + uuid.uuid4().hex[:6]
        resp = requests.post(BASE + '/rooms', headers={'Authorization': f'Bearer {admin_token}'}, json={'name': name, 'visibility': 'public'})
        assert resp.status_code == 200
        room = resp.json().get('room')
        room_ids.append(room['id'])

    # page 2, per_page=5
    r = requests.get(BASE + '/admin/rooms?per_page=5&page=2', headers={'Authorization': f'Bearer {admin_token}'})
    assert r.status_code == 200
    body = r.json()
    assert body.get('page') == 2
    assert body.get('per_page') == 5
    assert 'rooms' in body and isinstance(body['rooms'], list)
    assert len(body['rooms']) <= 5
    assert body.get('total', 0) >= 11

    # search for the special room by substring
    q = 'special-search-room'
    rs = requests.get(BASE + f'/admin/rooms?q={q}&per_page=10&page=1', headers={'Authorization': f'Bearer {admin_token}'})
    assert rs.status_code == 200
    sb = rs.json()
    assert 'rooms' in sb and isinstance(sb['rooms'], list)
    # found at least one matching room
    assert any(q in (r.get('name') or '') for r in sb['rooms'])
