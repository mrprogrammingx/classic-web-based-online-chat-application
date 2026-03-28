from fastapi.testclient import TestClient
from routers.app import app
import uuid


def test_sessions_list_and_revoke():
    client = TestClient(app)
    # create test user via register
    email = f'test+{uuid.uuid4().hex[:8]}@example.com'
    username = f'user_{uuid.uuid4().hex[:8]}'
    pw = 'pw1234'
    r = client.post('/register', json={'email': email, 'username': username, 'password': pw})
    assert r.status_code == 200
    # list sessions
    r2 = client.get('/sessions')
    assert r2.status_code == 200
    data = r2.json()
    assert 'sessions' in data and isinstance(data['sessions'], list)
    # revoke the first session
    if data['sessions']:
        first = data['sessions'][0]['jti']
        r3 = client.post('/sessions/revoke', json={'jti': first})
        assert r3.status_code == 200
        assert r3.json().get('ok') is True

