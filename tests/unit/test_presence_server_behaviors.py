import time
import os
import uuid
import pytest

# Time-based tests only work when the server was started with a small AFK threshold.
_server_afk = max(int(os.getenv('AFK_SECONDS', '60')), 5)
_needs_fast_afk = pytest.mark.skipif(
    _server_afk > 10,
    reason=f'time-based AFK test requires AFK_SECONDS ≤ 10 (got {_server_afk})',
)


def parse_jwt_no_verify(token: str):
    try:
        parts = token.split('.')
        import base64, json
        payload = parts[1]
        payload += '=' * (-len(payload) % 4)
        data = json.loads(base64.urlsafe_b64decode(payload))
        return data
    except Exception:
        return {}


def test_heartbeat_accepts_cookie_without_jti(client):
    """Simulate cookie-based session: login to set HttpOnly cookie then POST heartbeat without jti.
    The server should accept the heartbeat by using the authenticated token's jti as a fallback.
    """
    s = client
    email = f"cookie+{uuid.uuid4().hex}@example.com"
    username = 'cookieuser' + uuid.uuid4().hex[:6]
    pw = 'Secret123!'
    # register
    r = s.post('/register', json={'email': email, 'username': username, 'password': pw})
    assert r.status_code == 200
    # login to set cookie (HttpOnly token cookie)
    r2 = s.post('/login', json={'email': email, 'password': pw})
    assert r2.status_code == 200
    # pick a tab id and POST heartbeat without jti
    tab_id = 'cookie-tab-' + uuid.uuid4().hex[:6]
    r3 = s.post('/presence/heartbeat', json={'tab_id': tab_id})
    assert r3.status_code == 200
    # fetch /me to get user id then assert presence is online
    r4 = s.get('/me')
    assert r4.status_code == 200
    uid = r4.json().get('user', {}).get('id')
    assert uid
    st = s.get(f'/presence/{uid}').json().get('status')
    assert st == 'online'


@_needs_fast_afk
def test_presence_online_seconds_minimum_enforced(client):
    """Verify that the server enforces a minimum presence timeout (>= 5s).
    We send a heartbeat, wait slightly less than 5s (4s) and expect the user to still be 'online'.
    After waiting beyond 5s we expect AFK or offline.
    """
    s = client
    email = f"min+{uuid.uuid4().hex}@example.com"
    username = 'minuser' + uuid.uuid4().hex[:6]
    pw = 'Secret123!'
    r = s.post('/register', json={'email': email, 'username': username, 'password': pw})
    assert r.status_code == 200
    data = r.json()
    token = data.get('token')
    user = data.get('user')
    assert token and user
    payload = parse_jwt_no_verify(token)
    jti = payload.get('jti')
    tab_id = 'min-tab-' + uuid.uuid4().hex[:6]
    # send heartbeat with jti
    r2 = s.post('/presence/heartbeat', headers={'Authorization': f'Bearer {token}'}, json={'tab_id': tab_id, 'jti': jti})
    assert r2.status_code == 200
    # immediate status should be online
    st0 = s.get(f"/presence/{user['id']}").json().get('status')
    assert st0 == 'online'
    # wait slightly less than the enforced minimum (4s) -> should still be online
    time.sleep(4)
    st1 = s.get(f"/presence/{user['id']}").json().get('status')
    assert st1 == 'online'
    # wait beyond minimum (2 more seconds) -> should now be AFK or offline
    time.sleep(2)
    st2 = s.get(f"/presence/{user['id']}").json().get('status')
    assert st2 in ('AFK', 'offline')
