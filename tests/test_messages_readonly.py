import uuid
import uuid
import requests


BASE = 'http://127.0.0.1:8000'


def unique_email(prefix='user'):
    return f"{prefix}-{uuid.uuid4().hex[:8]}@example.com"


def _make_post(sess, path, **kwargs):
    return sess.post(sess.base_url + path, **kwargs)


def _make_get(sess, path, **kwargs):
    return sess.get(sess.base_url + path, **kwargs)


def test_message_history_readonly_on_ban(client):
    # create two users and sessions
    a_email = unique_email('a')
    b_email = unique_email('b')
    import requests as _requests
    cl_a = _requests.Session()
    cl_b = _requests.Session()
    cl_a.base_url = 'http://127.0.0.1:8000'
    cl_b.base_url = 'http://127.0.0.1:8000'

    # register
    r = _make_post(cl_a, '/register', json={'email': a_email, 'username': 'a_'+uuid.uuid4().hex[:6], 'password': 'pw'})
    assert r.status_code == 200
    a = r.json()['user']
    r = _make_post(cl_b, '/register', json={'email': b_email, 'username': 'b_'+uuid.uuid4().hex[:6], 'password': 'pw'})
    assert r.status_code == 200
    b = r.json()['user']

    # make them friends (mutual)
    r = _make_post(cl_a, '/friends/add', json={'friend_id': b['id']})
    assert r.status_code in (200, 409)
    r = _make_post(cl_b, '/friends/add', json={'friend_id': a['id']})
    assert r.status_code in (200, 409)

    # send a message from a -> b
    r = _make_post(cl_a, '/messages/send', json={'to_id': b['id'], 'text': 'hello b'})
    assert r.status_code == 200

    # history should be readable and not read-only yet
    r = _make_get(cl_a, f'/messages/history?with_id={b["id"]}')
    assert r.status_code == 200
    jr = r.json()
    assert jr.get('read_only') in (False, 0)
    msgs = jr.get('messages', [])
    assert any(m.get('text') == 'hello b' for m in msgs)

    # now a bans b
    r = _make_post(cl_a, '/ban', json={'banned_id': b['id']})
    assert r.status_code == 200

    # history should still be present but now read_only
    r = _make_get(cl_a, f'/messages/history?with_id={b["id"]}')
    assert r.status_code == 200
    jr = r.json()
    assert jr.get('read_only') is True
    msgs = jr.get('messages', [])
    assert any(m.get('text') == 'hello b' for m in msgs)

    # further sends from either side should be blocked
    r = _make_post(cl_a, '/messages/send', json={'to_id': b['id'], 'text': 'can you see this?'})
    assert r.status_code == 403
    r = _make_post(cl_b, '/messages/send', json={'to_id': a['id'], 'text': 'reply?'})
    assert r.status_code == 403
