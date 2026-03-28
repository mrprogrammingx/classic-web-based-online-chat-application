import uuid


def unique_email(prefix='user'):
    return f"{prefix}-{uuid.uuid4().hex[:8]}@example.com"


def test_personal_messaging_rule(client):
    # create two users with separate sessions to emulate different browsers
    import requests as _requests
    cl_a = _requests.Session()
    cl_b = _requests.Session()
    cl_a.base_url = client.s.base_url if hasattr(client, 's') else 'http://127.0.0.1:8000'
    cl_b.base_url = cl_a.base_url

    def _post(sess, path, **kwargs):
        return sess.post(sess.base_url + path, **kwargs)

    def _get(sess, path, **kwargs):
        return sess.get(sess.base_url + path, **kwargs)

    # register two users A and B
    a_email = unique_email('a')
    b_email = unique_email('b')
    r = _post(cl_a, '/register', json={'email': a_email, 'username': 'a_' + uuid.uuid4().hex[:6], 'password': 'pw'})
    assert r.status_code == 200
    a = r.json()['user']
    r = _post(cl_b, '/register', json={'email': b_email, 'username': 'b_' + uuid.uuid4().hex[:6], 'password': 'pw'})
    assert r.status_code == 200
    b = r.json()['user']

    # sending before being friends should be blocked
    r = _post(cl_a, '/messages/send', json={'to_id': b['id'], 'text': 'hello before friend'})
    assert r.status_code == 403

    # create mutual friendship (add from both sides)
    r = _post(cl_a, '/friends/add', json={'friend_id': b['id']})
    assert r.status_code in (200, 409)
    r = _post(cl_b, '/friends/add', json={'friend_id': a['id']})
    assert r.status_code in (200, 409)

    # now messaging should succeed
    r = _post(cl_a, '/messages/send', json={'to_id': b['id'], 'text': 'hello friend'})
    assert r.status_code == 200

    # dialog history should report read_only False (not banned)
    r = _get(cl_a, f'/messages/history?with_id={b["id"]}')
    assert r.status_code == 200
    jr = r.json()
    assert jr.get('read_only') in (False, 0)

    # B bans A -> messaging blocked and friendship removed
    r = _post(cl_b, '/ban', json={'banned_id': a['id']})
    assert r.status_code == 200

    # ensure friendship removed
    r = _get(cl_a, '/friends')
    assert r.status_code == 200
    assert all(f['id'] != b['id'] for f in r.json().get('friends', []))

    # both directions should be blocked now
    r = _post(cl_a, '/messages/send', json={'to_id': b['id'], 'text': 'after ban'})
    assert r.status_code == 403
    r = _post(cl_b, '/messages/send', json={'to_id': a['id'], 'text': 'from b after ban'})
    assert r.status_code == 403

    # dialog history should now be read_only
    r = _get(cl_a, f'/messages/history?with_id={b["id"]}')
    assert r.status_code == 200
    assert r.json().get('read_only') is True

    # B unbans A (only banner can unban)
    r = _post(cl_b, '/unban', json={'banned_id': a['id']})
    assert r.status_code == 200

    # still not friends -> messaging blocked
    r = _post(cl_a, '/messages/send', json={'to_id': b['id'], 'text': 'after unban'})
    assert r.status_code == 403

    # re-establish mutual friendship and verify messaging works again
    r = _post(cl_a, '/friends/add', json={'friend_id': b['id']})
    assert r.status_code in (200, 409)
    r = _post(cl_b, '/friends/add', json={'friend_id': a['id']})
    assert r.status_code in (200, 409)
    r = _post(cl_a, '/messages/send', json={'to_id': b['id'], 'text': 'final hello'})
    assert r.status_code == 200
