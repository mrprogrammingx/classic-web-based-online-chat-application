import uuid
import base64
import json


def parse_jwt_no_verify(token: str):
    try:
        parts = token.split('.')
        payload = parts[1]
        payload += '=' * (-len(payload) % 4)
        return json.loads(base64.urlsafe_b64decode(payload))
    except Exception:
        return {}


def test_refresh_and_batch_presence(client):
    # register
    email = f"test+{uuid.uuid4().hex}@example.com"
    username = 'tuser-' + uuid.uuid4().hex[:8]
    pw = 'Secret123!'
    r = client.post('/register', json={'email': email, 'username': username, 'password': pw})
    assert r.status_code == 200
    data = r.json()
    assert 'token' in data and 'user' in data
    token = data['token']
    user = data['user']

    # refresh using Authorization header
    headers = {'Authorization': f'Bearer {token}'}
    rr = client.post('/refresh', headers=headers)
    assert rr.status_code == 200
    rrj = rr.json()
    assert 'token' in rrj and 'user' in rrj

    # parse jti from token and send heartbeat
    payload = parse_jwt_no_verify(token)
    jti = payload.get('jti')
    assert jti
    tab_id = 'test-tab-' + uuid.uuid4().hex[:6]
    hb = client.post('/presence/heartbeat', headers=headers, json={'tab_id': tab_id, 'jti': jti})
    assert hb.status_code == 200

    # batch presence lookup (public endpoint)
    pres = client.get(f'/presence?ids={user["id"]}')
    assert pres.status_code == 200
    assert 'statuses' in pres.json()
    statuses = pres.json()['statuses']
    assert str(user['id']) in statuses

    # users lookup requires auth
    uresp = client.get(f'/users?ids={user["id"]}', headers=headers)
    assert uresp.status_code == 200
    users = uresp.json().get('users', [])
    assert any(u.get('id') == user['id'] and (u.get('username') == username) for u in users)
