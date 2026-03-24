import uuid
import os


def _reg_and_token(client, prefix='u'):
    suffix = str(uuid.uuid4())[:8]
    email = f'{prefix}_{suffix}@example.com'
    username = f'{prefix}_{suffix}'
    r = client.post('/register', json={'email': email, 'username': username, 'password': 'pw'})
    assert r.status_code == 200
    return r.json()['user'], r.json()['token']


def test_dialog_messages_with_file(client):
    a, ta = _reg_and_token(client, 'alice_mwf')
    b, tb = _reg_and_token(client, 'bob_mwf')

    # make them friends both ways
    client.s.headers.update({'Authorization': f'Bearer {ta}'})
    assert client.post('/friends/request', json={'username': b['username']}).status_code == 200
    client.s.headers.update({'Authorization': f'Bearer {tb}'})
    reqs = client.get('/friends/requests')
    reqs_json = reqs.json().get('requests', [])
    rid = None
    for r in reqs_json:
        if r.get('username') == a['username']:
            rid = r['id']
            break
    assert rid is not None
    assert client.post('/friends/requests/respond', json={'request_id': rid, 'action': 'accept'}).status_code == 200

    # alice sends a message with a file attached (atomic endpoint)
    client.s.headers.update({'Authorization': f'Bearer {ta}'})
    files = {'file': ('dlg.txt', b'hello dialog')}
    data = {'text': 'hi with file', 'comment': 'dlg note'}
    r = client.post(f'/dialogs/{b["id"]}/messages_with_file', files=files, data=data)
    assert r.status_code == 200
    payload = r.json()
    assert 'message' in payload
    assert payload['message'].get('text') == 'hi with file'
    assert 'file' in payload and payload['file'] is not None
    fmeta = payload['file']
    assert fmeta.get('original_filename') == 'dlg.txt'
    assert fmeta.get('comment') == 'dlg note'

    # bob fetches dialog history and should see the message with attached file metadata
    client.s.headers.update({'Authorization': f'Bearer {tb}'})
    h = client.get(f'/dialogs/{a["id"]}/messages')
    assert h.status_code == 200
    msgs = h.json().get('messages', [])
    assert any(m.get('text') == 'hi with file' and m.get('files') for m in msgs)

    # bob should be able to fetch the file using the provided url
    fid = fmeta['id']
    # file URL is returned as /dialogs/{other_id}/files/{fid}; call it as bob (participant)
    fr = client.get(f'/dialogs/{a["id"]}/files/{fid}')
    assert fr.status_code == 200
    assert fr.content == b'hello dialog'


def test_room_messages_with_file(client):
    s = client
    # register two users
    import time
    suffix = str(uuid.uuid4())[:8]
    r = s.post('/register', json={'email': f'a_{suffix}@example.com', 'username': f'a_{suffix}', 'password': 'pw'})
    assert r.status_code == 200
    a_tok = r.json().get('token')
    a_user = r.json().get('user')
    r = s.post('/register', json={'email': f'b_{suffix}@example.com', 'username': f'b_{suffix}', 'password': 'pw'})
    assert r.status_code == 200
    b_tok = r.json().get('token')
    b_user = r.json().get('user')
    ra = {'Authorization': f'Bearer {a_tok}'}
    rb = {'Authorization': f'Bearer {b_tok}'}

    # create a private room as a (invite b)
    r = s.post('/rooms', headers=ra, json={'name': f'testroom-mwf-{int(time.time())}', 'visibility': 'private'})
    assert r.status_code == 200
    room = r.json()['room']
    room_id = room['id']
    # invite b and accept
    r = s.post(f'/rooms/{room_id}/invite', headers=ra, json={'invitee_id': b_user['id']})
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

    # b posts a message with a file using the atomic endpoint
    s.s.headers.update({'Authorization': f'Bearer {b_tok}'})
    files = {'file': ('note.txt', b'note content')}
    data = {'text': 'room hello', 'comment': 'room note'}
    r = s.post(f'/rooms/{room_id}/messages_with_file', files=files, data=data)
    assert r.status_code == 200
    p = r.json()
    assert 'message' in p and 'file' in p
    assert p['message'].get('text') == 'room hello'
    fmeta = p['file']
    assert fmeta.get('original_filename') == 'note.txt'
    assert fmeta.get('comment') == 'room note'

    # file should be fetchable by a room member (a or b)
    fid = fmeta['id']
    # use a to fetch
    s.s.headers.update({'Authorization': f'Bearer {a_tok}'})
    fr = s.get(f'/rooms/{room_id}/files/{fid}')
    assert fr.status_code == 200
    assert fr.content == b'note content'
