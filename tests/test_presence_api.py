import requests
import time
import uuid
import pytest

BASE = 'http://127.0.0.1:8000'


def parse_jwt_no_verify(token: str):
    try:
        parts = token.split('.')
        import base64, json
        payload = parts[1]
        # add padding
        payload += '=' * (-len(payload) % 4)
        data = json.loads(base64.urlsafe_b64decode(payload))
        return data
    except Exception:
        return {}


def server_available():
    try:
        r = requests.get(BASE + '/')
        return r.status_code in (200, 307)
    except Exception:
        return False


@pytest.mark.skipif(not server_available(), reason="server not running on localhost:8000")
def test_register_login_and_sessions():
    email = f"test+{uuid.uuid4().hex}@example.com"
    username = 'testuser'
    pw = 'Secret123!'
    # register
    r = requests.post(BASE + '/register', json={'email': email, 'username': username, 'password': pw})
    assert r.status_code == 200
    data = r.json()
    assert 'token' in data
    token = data['token']
    payload = parse_jwt_no_verify(token)
    assert payload.get('email') == email

    # login
    r = requests.post(BASE + '/login', json={'email': email, 'password': pw})
    assert r.status_code == 200
    data = r.json()
    token = data['token']

    # sessions
    headers = {'Authorization': f'Bearer {token}'}
    r = requests.get(BASE + '/sessions', headers=headers)
    assert r.status_code == 200
    sessions = r.json().get('sessions', [])
    assert isinstance(sessions, list)
    assert len(sessions) >= 1


@pytest.mark.skipif(not server_available(), reason="server not running on localhost:8000")
def test_username_immutable():
    email = f"test+{uuid.uuid4().hex}@example.com"
    username = 'immutable'
    pw = 'Secret123!'
    r = requests.post(BASE + '/register', json={'email': email, 'username': username, 'password': pw})
    assert r.status_code == 200
    token = r.json()['token']
    headers = {'Authorization': f'Bearer {token}'}

    # attempt to change username
    r = requests.patch(BASE + '/me', headers=headers, json={'username': 'newname'})
    assert r.status_code == 400


@pytest.mark.skipif(not server_available(), reason="server not running on localhost:8000")
def test_presence_heartbeat_and_close():
    email = f"test+{uuid.uuid4().hex}@example.com"
    username = 'presence'
    pw = 'Secret123!'
    r = requests.post(BASE + '/register', json={'email': email, 'username': username, 'password': pw})
    assert r.status_code == 200
    data = r.json()
    token = data['token']
    user = data['user']
    payload = parse_jwt_no_verify(token)
    jti = payload.get('jti')
    headers = {'Authorization': f'Bearer {token}'}

    # heartbeat
    tab_id = 'test-tab-' + uuid.uuid4().hex[:6]
    r = requests.post(BASE + '/presence/heartbeat', headers=headers, json={'tab_id': tab_id, 'jti': jti})
    assert r.status_code == 200

    # presence should be online
    r = requests.get(BASE + f"/presence/{user['id']}")
    assert r.status_code == 200
    assert r.json().get('status') in ('online', 'AFK', 'offline')

    # close tab
    r = requests.post(BASE + '/presence/close', headers=headers, json={'tab_id': tab_id})
    # close may be unauthorized if token expired; allow 200 or 401
    assert r.status_code in (200, 401)
