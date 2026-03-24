import uuid
import time


def _reg_and_token(client, prefix='u'):
    suffix = str(uuid.uuid4())[:8]
    email = f'{prefix}_{suffix}@example.com'
    username = f'{prefix}_{suffix}'
    r = client.post('/register', json={'email': email, 'username': username, 'password': 'pw'})
    assert r.status_code == 200
    return r.json()['user'], r.json()['token']


def test_room_pagination(client):
    owner, ot = _reg_and_token(client, 'own_pag')
    user, ut = _reg_and_token(client, 'u_pag')

    client.s.headers.update({'Authorization': f'Bearer {ot}'})
    rn = f"pagroom_{uuid.uuid4().hex[:8]}"
    rc = client.post('/rooms', json={'name': rn, 'visibility': 'public'})
    rid = rc.json()['room']['id']
    client.post(f'/rooms/{rid}/members/add', json={'user_id': user['id']})

    client.s.headers.update({'Authorization': f'Bearer {ut}'})
    # post 120 messages
    for i in range(120):
        client.post(f'/rooms/{rid}/messages', json={'text': f'msg {i}'})

    # fetch first page (limit 50)
    got = client.get(f'/rooms/{rid}/messages?limit=50&offset=0')
    assert got.status_code == 200
    msgs = got.json()['messages']
    assert len(msgs) == 50
    # fetch next page
    got2 = client.get(f'/rooms/{rid}/messages?limit=50&offset=50')
    assert got2.status_code == 200
    assert len(got2.json()['messages']) == 50
    # final page
    got3 = client.get(f'/rooms/{rid}/messages?limit=50&offset=100')
    assert got3.status_code == 200
    assert len(got3.json()['messages']) == 20


def test_dialog_delivery_on_open(client):
    a, ta = _reg_and_token(client, 'a_del')
    b, tb = _reg_and_token(client, 'b_del')

    # make friends
    client.s.headers.update({'Authorization': f'Bearer {ta}'})
    assert client.post('/friends/request', json={'username': b['username']}).status_code == 200
    client.s.headers.update({'Authorization': f'Bearer {tb}'})
    reqs = client.get('/friends/requests').json().get('requests', [])
    req_id = next((r['id'] for r in reqs if r['username'] == a['username']), None)
    assert req_id is not None
    assert client.post('/friends/requests/respond', json={'request_id': req_id, 'action': 'accept'}).status_code == 200

    # a sends messages while b is offline (we won't fetch as b)
    client.s.headers.update({'Authorization': f'Bearer {ta}'})
    for i in range(5):
        client.post(f'/dialogs/{b["id"]}/messages', json={'text': f'hi {i}'})

    # b opens dialog and should receive messages; delivered_at should be set on those messages
    client.s.headers.update({'Authorization': f'Bearer {tb}'})
    h = client.get(f'/dialogs/{a["id"]}/messages')
    assert h.status_code == 200
    msgs = h.json()['messages']
    assert len(msgs) == 5
    # all messages sent to b should now have delivered_at
    for m in msgs:
        if m['to_id'] == b['id']:
            assert 'delivered_at' in m
