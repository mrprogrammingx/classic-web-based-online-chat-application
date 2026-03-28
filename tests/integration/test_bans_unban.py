import uuid

import requests


BASE = 'http://127.0.0.1:8000'


def unique_email(prefix='user'):
    return f"{prefix}-{uuid.uuid4().hex[:8]}@example.com"


def test_bans_and_unban_flow(client):
    # Create two users in separate sessions to emulate two browsers
    import requests as _requests
    alice_sess = _requests.Session()
    bob_sess = _requests.Session()
    # attach base_url similar to other integration tests
    alice_sess.base_url = client.s.base_url if hasattr(client, 's') else BASE
    bob_sess.base_url = alice_sess.base_url

    def _post(sess, path, **kwargs):
        return sess.post(sess.base_url + path, **kwargs)

    def _get(sess, path, **kwargs):
        return sess.get(sess.base_url + path, **kwargs)

    # register alice and bob
    alice_email = unique_email('alice')
    bob_email = unique_email('bob')
    alice_un = 'alice_' + uuid.uuid4().hex[:6]
    bob_un = 'bob_' + uuid.uuid4().hex[:6]

    r = _post(alice_sess, '/register', json={'email': alice_email, 'username': alice_un, 'password': 'pw'})
    assert r.status_code == 200
    alice = r.json()['user']

    r = _post(bob_sess, '/register', json={'email': bob_email, 'username': bob_un, 'password': 'pw'})
    assert r.status_code == 200
    bob = r.json()['user']

    # Alice bans Bob
    r = _post(alice_sess, '/ban', json={'banned_id': bob['id']})
    assert r.status_code == 200

    # GET /bans should show Bob for Alice
    r = _get(alice_sess, '/bans')
    assert r.status_code == 200
    banned = r.json().get('banned', [])
    assert any(b.get('banned_id') == bob['id'] for b in banned)

    # check /bans/check returns true
    r = _get(alice_sess, f'/bans/check?other_id={bob["id"]}')
    assert r.status_code == 200
    assert r.json().get('banned') is True

    # Unban Bob
    r = _post(alice_sess, '/unban', json={'banned_id': bob['id']})
    assert r.status_code == 200

    # Now /bans should no longer include Bob
    r = _get(alice_sess, '/bans')
    assert r.status_code == 200
    banned = r.json().get('banned', [])
    assert all(b.get('banned_id') != bob['id'] for b in banned)

    # /bans/check should be false
    r = _get(alice_sess, f'/bans/check?other_id={bob["id"]}')
    assert r.status_code == 200
    assert r.json().get('banned') is False

    # After unban, Bob should be able to send a friend request to Alice
    r = _post(bob_sess, '/friends/request', json={'friend_id': alice['id'], 'message': 'hello after unban'})
    assert r.status_code == 200
