import uuid
import time


def _reg_and_token(client, prefix='u'):
    suffix = str(uuid.uuid4())[:8]
    email = f'{prefix}_{suffix}@example.com'
    username = f'{prefix}_{suffix}'
    r = client.post('/register', json={'email': email, 'username': username, 'password': 'pw'})
    assert r.status_code == 200
    return r.json()['user'], r.json()['token']


def test_room_reply_to_with_file_preserved(client):
    s = client
    # register two users and create a room
    a, ta = _reg_and_token(s, 'ra')
    b, tb = _reg_and_token(s, 'rb')
    ra = {'Authorization': f'Bearer {ta}'}
    rb = {'Authorization': f'Bearer {tb}'}
    r = s.post('/rooms', headers=ra, json={'name': f'replyroom-{int(time.time())}', 'visibility': 'private'})
    assert r.status_code == 200
    room = r.json()['room']
    room_id = room['id']
    # invite b and accept
    r = s.post(f'/rooms/{room_id}/invite', headers=ra, json={'invitee_id': b['id']})
    assert r.status_code == 200
    r = s.get(f'/rooms/{room_id}/invites', headers=rb)
    invs = r.json().get('invites', [])
    invite_id = None
    for inv in invs:
        if inv.get('room_id') == room_id:
            invite_id = inv['id']
            break
    assert invite_id is not None
    r = s.post(f'/rooms/{room_id}/invites/{invite_id}/accept', headers=rb)
    assert r.status_code == 200

    # a posts a message
    s.s.headers.update({'Authorization': f'Bearer {ta}'})
    r = s.post(f'/rooms/{room_id}/messages', headers=ra, json={'text': 'original msg'})
    assert r.status_code == 200
    mid = r.json()['message']['id']

    # b replies with a file using messages_with_file
    s.s.headers.update({'Authorization': f'Bearer {tb}'})
    files = {'file': ('reply.txt', b'reply content')}
    data = {'text': 'replying with file', 'reply_to': str(mid)}
    r = s.post(f'/rooms/{room_id}/messages_with_file', headers=rb, files=files, data=data)
    assert r.status_code == 200
    # fetch messages and assert the reply is linked
    r = s.get(f'/rooms/{room_id}/messages', headers=rb)
    assert r.status_code == 200
    msgs = r.json().get('messages', [])
    found = False
    for m in msgs:
        if m.get('text') == 'replying with file':
            # reply_to should equal mid and reply preview should be present
            assert m.get('reply_to') == mid
            assert m.get('reply') is not None
            found = True
            break
    assert found
