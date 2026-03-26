import time
import requests
import uuid

BASE = 'http://127.0.0.1:8000'

# Helpers

import uuid


def unique_email(prefix='user'):
    return f"{prefix}-{uuid.uuid4().hex[:8]}@example.com"


def create_user(client, username=None, email=None, password='pw'):
    if not email:
        email = unique_email('u')
    if not username:
        username = email.split('@')[0]
    r = client.post('/register', json={'email': email, 'username': username, 'password': password})
    assert r.status_code == 200
    return r.json()['user']


def login(client, email, password='pw'):
    r = client.post('/login', json={'email': email, 'password': password})
    assert r.status_code == 200
    return r.json()['user']


def test_friend_request_accept_reject_and_ban_flow(client):
    # create two users: alice and bob
    alice_email = unique_email('alice')
    bob_email = unique_email('bob')
    alice_un = 'alice_' + uuid.uuid4().hex[:6]
    bob_un = 'bob_' + uuid.uuid4().hex[:6]
    # register/login as alice
    # use two distinct sessions to emulate separate browsers
    import requests as _requests
    client_alice = _requests.Session()
    client_bob = _requests.Session()
    # attach base URL onto the session-like helper used by our client fixture
    client_alice.base_url = client.s.base_url if hasattr(client, 's') else 'http://127.0.0.1:8000'
    client_bob.base_url = client_alice.base_url

    def _post(sess, path, **kwargs):
        return sess.post(sess.base_url + path, **kwargs)

    def _get(sess, path, **kwargs):
        return sess.get(sess.base_url + path, **kwargs)

    r = _post(client_alice, '/register', json={'email': alice_email, 'username': alice_un, 'password': 'pw'})
    assert r.status_code == 200
    alice = r.json()['user']

    r = _post(client_bob, '/register', json={'email': bob_email, 'username': bob_un, 'password': 'pw'})
    assert r.status_code == 200
    bob = r.json()['user']

    # Alice sends a friend request to Bob by username
    r = _post(client_alice, '/friends/request', json={'username': bob['username'], 'message': 'hi bob'})
    assert r.status_code == 200

    # Bob should see one incoming request (simulate bob's session)
    r = _get(client_bob, '/friends/requests')
    assert r.status_code == 200
    reqs = r.json().get('requests', [])
    assert len(reqs) >= 1
    req = reqs[-1]
    assert req['from_id'] == alice['id']
    req_id = req['id']

    # Bob rejects the request
    r = _post(client_bob, '/friends/requests/respond', json={'request_id': req_id, 'action': 'reject'})
    assert r.status_code == 200

    # Ensure no friendship exists
    r = _get(client_bob, '/friends')
    assert r.status_code == 200
    friends = r.json().get('friends', [])
    assert all(f['id'] != alice['id'] for f in friends)

    # Alice sends another friend request
    r = _post(client_alice, '/friends/request', json={'friend_id': bob['id'], 'message': 'hi again'})
    assert r.status_code == 200

    # Bob accepts it
    r = _get(client_bob, '/friends/requests')
    reqs = r.json().get('requests', [])
    ids = [rq['id'] for rq in reqs if rq['from_id'] == alice['id']]
    assert ids
    rid = ids[-1]
    r = _post(client_bob, '/friends/requests/respond', json={'request_id': rid, 'action': 'accept'})
    assert r.status_code == 200

    # Both should list each other as friends
    r = _get(client_bob, '/friends')
    assert any(f['id'] == alice['id'] for f in r.json().get('friends', []))
    r = _get(client_alice, '/friends')
    assert any(f['id'] == bob['id'] for f in r.json().get('friends', []))

    # Now Alice bans Bob
    r = _post(client_alice, '/ban', json={'banned_id': bob['id']})
    assert r.status_code == 200

    # Friendship should be removed
    r = _get(client_alice, '/friends')
    assert all(f['id'] != bob['id'] for f in r.json().get('friends', []))
    r = _get(client_bob, '/friends')
    assert all(f['id'] != alice['id'] for f in r.json().get('friends', []))

    # Bob trying to send friend request to Alice should be blocked
    r = _post(client_bob, '/friends/request', json={'friend_id': alice['id'], 'message': 'please'})
    assert r.status_code == 403

    # check ban endpoint
    r = _get(client_alice, f'/bans/check?other_id={bob["id"]}')
    assert r.status_code == 200
    assert r.json().get('banned') is True


def test_friend_request_edge_cases_and_message_enforcement(client):
    # create users
    a_email = unique_email('a')
    b_email = unique_email('b')
    import requests as _requests
    cl_a = _requests.Session()
    cl_b = _requests.Session()
    cl_a.base_url = 'http://127.0.0.1:8000'
    cl_b.base_url = 'http://127.0.0.1:8000'
    def _post(sess, path, **kwargs):
        return sess.post(sess.base_url + path, **kwargs)
    def _get(sess, path, **kwargs):
        return sess.get(sess.base_url + path, **kwargs)

    r = _post(cl_a, '/register', json={'email': a_email, 'username': 'a_'+uuid.uuid4().hex[:6], 'password': 'pw'})
    a = r.json()['user']
    r = _post(cl_b, '/register', json={'email': b_email, 'username': 'b_'+uuid.uuid4().hex[:6], 'password': 'pw'})
    b = r.json()['user']

    # request-to-self should be rejected
    r = _post(cl_a, '/friends/request', json={'friend_id': a['id'], 'message': 'self'})
    assert r.status_code == 400

    # duplicate request: send request, then send again
    r = _post(cl_a, '/friends/request', json={'friend_id': b['id'], 'message': 'hello'})
    assert r.status_code == 200
    r = _post(cl_a, '/friends/request', json={'friend_id': b['id'], 'message': 'hello again'})
    assert r.status_code in (200, 409)

    # accept to become friends
    # fetch request id as 'b' viewing incoming
    r = _get(cl_b, '/friends/requests')
    reqs = r.json().get('requests', [])
    ids = [rq['id'] for rq in reqs if rq['from_id'] == a['id']]
    if ids:
        rid = ids[-1]
        r = _post(cl_b, '/friends/requests/respond', json={'request_id': rid, 'action': 'accept'})


    # ensure message sending fails if not friends
    # create c (not friend)
    c_email = unique_email('c')
    r = client.post('/register', json={'email': c_email, 'username': 'c_'+uuid.uuid4().hex[:6], 'password': 'pw'})
    c = r.json()['user']
    r = _post(cl_a, '/messages/send', json={'to_id': c['id'], 'text': 'hi'})
    assert r.status_code == 403

    # message sending should succeed between friends: create mutual friendship a<->b explicitly
    # insert friend rows via API
    r = _post(cl_a, '/friends/add', json={'friend_id': b['id']})
    r = _post(cl_b, '/friends/add', json={'friend_id': a['id']})
    # now send message a->b
    r = _post(cl_a, '/messages/send', json={'to_id': b['id'], 'text': 'hello bob'})
    assert r.status_code == 200

    # ban-by-other-direction: if b bans a, then a cannot message b and friend removed
    r = _post(cl_b, '/ban', json={'banned_id': a['id']})
    assert r.status_code == 200
    r = _post(cl_a, '/messages/send', json={'to_id': b['id'], 'text': 'are you there?'})
    assert r.status_code == 403
