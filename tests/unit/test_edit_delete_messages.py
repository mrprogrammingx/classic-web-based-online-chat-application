import uuid


def _reg_and_auth(client, prefix='u'):
    suffix = str(uuid.uuid4())[:8]
    email = f'{prefix}_{suffix}@example.com'
    username = f'{prefix}_{suffix}'
    r = client.post('/register', json={'email': email, 'username': username, 'password': 'pass'})
    assert r.status_code == 200
    token = r.json()['token']
    client.s.headers.update({'Authorization': f'Bearer {token}'})
    return r.json()['user']


def test_author_can_edit_and_delete_message(client):
    # register owner and create room
    owner = _reg_and_auth(client, 'owner')
    room = client.post('/rooms', json={'name': f'room_edit_{str(uuid.uuid4())[:6]}'}).json()['room']
    rid = room['id']
    # post a message
    post = client.post(f'/rooms/{rid}/messages', json={'text': 'original'})
    assert post.status_code == 200
    msg = post.json()['message']
    mid = msg['id']
    # edit message
    edit = client.post(f'/rooms/{rid}/messages/{mid}/edit', json={'text': 'edited'})
    assert edit.status_code == 200
    assert edit.json()['message']['text'] == 'edited'
    # delete message
    dl = client.delete(f'/rooms/{rid}/messages/{mid}')
    assert dl.status_code == 200
    # verify gone
    lm = client.get(f'/rooms/{rid}/messages').json()
    assert all(m['id'] != mid for m in lm.get('messages', []))


def test_non_author_cannot_edit_but_author_or_admin_can_delete(client):
    # register author and post message
    author = _reg_and_auth(client, 'author')
    room = client.post('/rooms', json={'name': f'room_edit2_{str(uuid.uuid4())[:6]}'}).json()['room']
    rid = room['id']
    p = client.post(f'/rooms/{rid}/messages', json={'text': 'hello'})
    assert p.status_code == 200
    mid = p.json()['message']['id']
    # register another user and attempt edit/delete
    other = _reg_and_auth(client, 'other')
    ed = client.post(f'/rooms/{rid}/messages/{mid}/edit', json={'text': 'x'})
    assert ed.status_code == 403
    dl = client.delete(f'/rooms/{rid}/messages/{mid}')
    # not allowed for non-author/non-admin
    assert dl.status_code == 403
