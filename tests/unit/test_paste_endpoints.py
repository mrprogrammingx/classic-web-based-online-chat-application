import base64
import uuid
import time


def _reg_and_token(client, prefix='u'):
    suffix = str(uuid.uuid4())[:8]
    email = f'{prefix}_{suffix}@example.com'
    username = f'{prefix}_{suffix}'
    r = client.post('/register', json={'email': email, 'username': username, 'password': 'pw'})
    assert r.status_code == 200
    return r.json()['user'], r.json()['token']


def test_dialog_paste_and_revoked_access(client):
    a, ta = _reg_and_token(client, 'paste_a')
    b, tb = _reg_and_token(client, 'paste_b')

    # make friends both ways
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

    # paste a file from a to b
    client.s.headers.update({'Authorization': f'Bearer {ta}'})
    data_url = 'data:text/plain;base64,' + base64.b64encode(b'hello from paste').decode()
    r = client.post(f'/dialogs/{b["id"]}/files/paste', headers={'Authorization': f'Bearer {ta}'}, json={'filename': 'pasted.txt', 'data': data_url, 'comment': 'pasted note'})
    assert r.status_code == 200
    f = r.json().get('file')
    assert f.get('original_filename') == 'pasted.txt'
    assert f.get('comment') == 'pasted note'

    # break friendship and ensure access revoked
    r = client.post('/friends/remove', headers={'Authorization': f'Bearer {ta}'}, json={'friend_id': b['id']})
    assert r.status_code == 200
    # b should no longer list or fetch the file
    client.s.headers.update({'Authorization': f'Bearer {tb}'})
    r = client.get(f'/dialogs/{a["id"]}/files')
    assert r.status_code == 403
    fid = f['id']
    r = client.get(f'/dialogs/{a["id"]}/files/{fid}')
    assert r.status_code == 403


def test_room_paste_and_revoked_access(client):
    s = client
    suffix = str(uuid.uuid4())[:8]
    # register users
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

    # create private room and invite b
    r = s.post('/rooms', headers=ra, json={'name': f'paste-room-{int(time.time())}', 'visibility': 'private'})
    assert r.status_code == 200
    room = r.json().get('room')
    room_id = room['id']
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

    # b pastes a file into the room
    data_url = 'data:text/plain;base64,' + base64.b64encode(b'room paste content').decode()
    r = s.post(f'/rooms/{room_id}/files/paste', headers=rb, json={'filename': 'room.txt', 'data': data_url, 'comment': 'room paste'})
    assert r.status_code == 200
    f = r.json().get('file')
    assert f.get('original_filename') == 'room.txt'
    assert f.get('comment') == 'room paste'

    # owner removes b -> treated as ban; b should not be able to list or fetch
    r = s.post(f'/rooms/{room_id}/members/remove', headers=ra, json={'user_id': b_user['id']})
    assert r.status_code == 200
    r = s.get(f'/rooms/{room_id}/files', headers=rb)
    assert r.status_code == 403
    fid = f['id']
    r = s.get(f'/rooms/{room_id}/files/{fid}', headers=rb)
    assert r.status_code == 403
