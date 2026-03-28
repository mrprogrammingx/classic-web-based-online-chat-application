import uuid
import sqlite3
import requests
import pytest
from test_auth_admin import BASE, unique_email, server_available


@pytest.mark.skipif(not server_available(), reason="server not running on localhost:8000")
def test_admin_messages_pagination_and_search():
    admin_email = unique_email()
    admin_username = 'adm-msgs-' + uuid.uuid4().hex[:6]
    pw = 'adminpw'
    r = requests.post(BASE + '/register', json={'email': admin_email, 'username': admin_username, 'password': pw})
    assert r.status_code == 200
    admin_token = r.json().get('token'); admin_user = r.json().get('user')
    from core.config import DB_PATH
    conn = sqlite3.connect(DB_PATH); cur = conn.cursor(); cur.execute('UPDATE users SET is_admin = 1 WHERE id = ?', (admin_user['id'],)); conn.commit(); conn.close()

    # create a room and post 13 messages, giving one message a distinctive substring
    resp = requests.post(BASE + '/rooms', headers={'Authorization': f'Bearer {admin_token}'}, json={'name': 'msgs-admin-room-' + uuid.uuid4().hex[:4], 'visibility': 'public'})
    assert resp.status_code == 200
    room = resp.json().get('room')
    rid = room['id']

    special_text = 'unique-search-token-' + uuid.uuid4().hex[:6]
    for i in range(13):
        text = f'msg {i}'
        if i == 5:
            text = 'contains ' + special_text + ' in middle'
        p = requests.post(BASE + f'/rooms/{rid}/messages', headers={'Authorization': f'Bearer {admin_token}'}, json={'text': text})
        assert p.status_code == 200

    # fetch page 2 with per_page=5
    r = requests.get(BASE + '/admin/messages?per_page=5&page=2', headers={'Authorization': f'Bearer {admin_token}'})
    assert r.status_code == 200
    body = r.json()
    assert body.get('page') == 2
    assert body.get('per_page') == 5
    assert 'messages' in body and isinstance(body['messages'], list)
    assert len(body['messages']) <= 5
    assert body.get('total', 0) >= 13

    # search for the special message text
    q = special_text
    rs = requests.get(BASE + f'/admin/messages?q={q}&per_page=10&page=1', headers={'Authorization': f'Bearer {admin_token}'})
    assert rs.status_code == 200
    sb = rs.json()
    assert 'messages' in sb and isinstance(sb['messages'], list)
    assert any((q in (m.get('text') or '')) for m in sb['messages'])
