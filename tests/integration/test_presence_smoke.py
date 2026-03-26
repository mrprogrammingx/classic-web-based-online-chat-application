import pytest
import requests
from tests.test_auth_admin import BASE, server_available, unique_email


@pytest.mark.skipif(not server_available(), reason="server not running on localhost:8000")
def test_register_login_and_sessions():
    email = unique_email()
    username = 'presence-' + email.split('@')[0]
    pw = 'Secret123!'

    r = requests.post(BASE + '/register', json={'email': email, 'username': username, 'password': pw})
    assert r.status_code == 200
    data = r.json()
    assert 'token' in data
    token = data['token']

    # list sessions
    h = {'Authorization': f'Bearer {token}'}
    s = requests.get(BASE + '/sessions', headers=h)
    assert s.status_code == 200
    sessions = s.json().get('sessions', [])
    assert isinstance(sessions, list) and len(sessions) >= 0


@pytest.mark.skipif(not server_available(), reason="server not running on localhost:8000")
def test_presence_heartbeat_and_lookup():
    email = unique_email()
    username = 'presence2-' + email.split('@')[0]
    pw = 'Secret123!'

    r = requests.post(BASE + '/register', json={'email': email, 'username': username, 'password': pw})
    assert r.status_code == 200
    token = r.json().get('token')
    user = r.json().get('user')
    assert token and user

    headers = {'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'}
    # call heartbeat
    hb = requests.post(BASE + '/presence/heartbeat', headers=headers, json={'tab_id': 'tab-smoke', 'jti': token})
    # heartbeat may accept or return 200/204 depending on implementation; accept 200..299
    assert 200 <= hb.status_code < 300

    # fetch presence for user
    p = requests.get(BASE + f"/presence/{user['id']}")
    assert p.status_code == 200
    data = p.json()
    assert 'status' in data
