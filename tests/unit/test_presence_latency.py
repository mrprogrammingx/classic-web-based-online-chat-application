import time
import uuid


def _reg_and_token(client, prefix):
    import uuid
    s = client
    suffix = str(uuid.uuid4())[:8]
    email = f'{prefix}_{suffix}@example.com'
    r = s.post('/register', json={'email': email, 'username': f'{prefix}_{suffix}', 'password': 'pass'})
    assert r.status_code == 200
    return r.json()['user'], r.json()['token']


def test_presence_transitions(client):
    s = client
    user, token = _reg_and_token(s, 'presence')
    s.s.headers.update({'Authorization': f'Bearer {token}'})
    # simulate a tab heartbeat
    tab_id = 'tab-' + str(int(time.time()*1000))
    # extract jti from token payload without verification
    def parse_jwt_no_verify(tok: str):
        try:
            parts = tok.split('.')
            import base64, json
            payload = parts[1]
            payload += '=' * (-len(payload) % 4)
            data = json.loads(base64.urlsafe_b64decode(payload))
            return data
        except Exception:
            return {}

    payload = parse_jwt_no_verify(token)
    jti = payload.get('jti')
    # first heartbeat
    r = s.post('/presence/heartbeat', json={'tab_id': tab_id, 'jti': jti})
    assert r.status_code == 200
    # should be online immediately
    st = s.get(f"/presence/{user['id']}").json()['status']
    assert st == 'online'
    # wait slightly longer than PRESENCE_ONLINE_SECONDS to become AFK
    time.sleep(4)
    st2 = s.get(f"/presence/{user['id']}").json()['status']
    assert st2 in ('AFK', 'offline')
    # close tab
    r = s.post('/presence/close', json={'tab_id': tab_id})
    assert r.status_code == 200
    st3 = s.get(f"/presence/{user['id']}").json()['status']
    assert st3 == 'offline'
