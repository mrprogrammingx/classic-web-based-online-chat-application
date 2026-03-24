import uuid
import os
import time


def _reg_and_token(client, prefix='u'):
    suffix = str(uuid.uuid4())[:8]
    email = f'{prefix}_{suffix}@example.com'
    username = f'{prefix}_{suffix}'
    r = client.post('/register', json={'email': email, 'username': username, 'password': 'pw'})
    assert r.status_code == 200
    return r.json()['user'], r.json()['token']


def _uploads_dir():
    return os.path.join(os.getcwd(), os.getenv('TEST_UPLOAD_DIR', 'uploads'))


def _cleanup_path(path):
    try:
        if not path:
            return
        if os.path.isabs(path):
            p = path
        else:
            p = os.path.join(_uploads_dir(), path)
            if not os.path.exists(p):
                legacy = os.path.join(os.getcwd(), 'uploads', path)
                if os.path.exists(legacy):
                    p = legacy
        if os.path.exists(p):
            os.remove(p)
    except Exception:
        pass


def test_attach_to_self_dialog_bad_request(client):
    u, tok = _reg_and_token(client, 'selftest')
    client.s.headers.update({'Authorization': f'Bearer {tok}'})
    files = {'file': ('me.txt', b'me')}
    r = client.post(f'/dialogs/{u["id"]}/messages_with_file', files=files, data={'text': 'hi'})
    assert r.status_code == 400


def test_dialog_messages_with_large_text_rejected(client):
    a, ta = _reg_and_token(client, 'alice_big')
    b, tb = _reg_and_token(client, 'bob_big')
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

    # send a message with text > 3KB via messages_with_file
    client.s.headers.update({'Authorization': f'Bearer {ta}'})
    big = 'x' * (3 * 1024 + 10)
    files = {'file': ('big.txt', b'big')}
    r = client.post(f'/dialogs/{b["id"]}/messages_with_file', files=files, data={'text': big})
    # should reject due to text size
    assert r.status_code == 400


def test_room_messages_with_file_not_member_and_banned(client):
    s = client
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

    # create private room as a
    r = s.post('/rooms', headers=ra, json={'name': f'tr-edge-{int(time.time())}', 'visibility': 'private'})
    assert r.status_code == 200
    room = r.json()['room']
    room_id = room['id']

    # b (not invited) tries to post with file -> forbidden
    s.s.headers.update({'Authorization': f'Bearer {b_tok}'})
    files = {'file': ('x.txt', b'x')}
    r = s.post(f'/rooms/{room_id}/messages_with_file', files=files, data={'text': 'hi'})
    assert r.status_code == 403

    # invite b and accept, then owner bans b and b should be forbidden
    s.s.headers.update({'Authorization': f'Bearer {a_tok}'})
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

    # now owner bans b
    s.s.headers.update({'Authorization': f'Bearer {a_tok}'})
    r = s.post(f'/rooms/{room_id}/ban', headers=ra, json={'user_id': b_user['id']})
    assert r.status_code == 200

    # b attempts to post with file -> 403
    s.s.headers.update({'Authorization': f'Bearer {b_tok}'})
    r = s.post(f'/rooms/{room_id}/messages_with_file', files=files, data={'text': 'you are banned'})
    assert r.status_code == 403

