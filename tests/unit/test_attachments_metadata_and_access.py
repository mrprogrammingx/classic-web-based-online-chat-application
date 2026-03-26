import base64
import time

import pytest


def test_room_attachment_metadata_and_revoked_access(client):
    # create users, rooms via existing fixtures or flow in tests (reuse simple flows from other tests)
    # We'll register two users, create a room, add other as member, upload file with comment, then remove member and assert access revoked.
    s = client
    # create users
    import uuid
    suffix = str(uuid.uuid4())[:8]
    a_email = f'a_{suffix}@example.com'
    b_email = f'b_{suffix}@example.com'
    r = s.post('/register', json={'email': a_email, 'username': f'a_{suffix}', 'password': 'pass'})
    assert r.status_code == 200
    a_tok = r.json().get('token')
    a_user = r.json().get('user')
    r = s.post('/register', json={'email': b_email, 'username': f'b_{suffix}', 'password': 'pass'})
    assert r.status_code == 200
    b_tok = r.json().get('token')
    b_user = r.json().get('user')
    ra = {'Authorization': f'Bearer {a_tok}'}
    rb = {'Authorization': f'Bearer {b_tok}'}
    # create room as a1
    r = s.post('/rooms', headers=ra, json={'name': f'testroom-{int(time.time())}', 'visibility': 'private'})
    assert r.status_code == 200
    room = r.json()['room']
    room_id = room['id']
    # invite b1 and accept
    r = s.post(f'/rooms/{room_id}/invite', headers=ra, json={'invitee_id': b_user['id']})
    assert r.status_code == 200
    # find invite id for invitee
    r = s.get(f'/rooms/{room_id}/invites', headers=rb)
    assert r.status_code == 200
    invs = r.json().get('invites', [])
    invite_id = None
    for inv in invs:
        if inv.get('room_id') == room_id:
            invite_id = inv['id']
            break
    assert invite_id is not None
    r = s.post(f'/rooms/{room_id}/invites/{invite_id}/accept', headers=rb)
    assert r.status_code == 200
    # b1 uploads a file with comment
    files = {'file': ('hello.txt', b'hello world')}
    r = s.post(f'/rooms/{room_id}/files', headers=rb, files=files)
    assert r.status_code == 200
    data = r.json()['file']
    assert 'original_filename' in data
    # upload with comment via multipart
    files = {'file': ('note.txt', b'note')}
    r = s.post(f'/rooms/{room_id}/files', headers=rb, files=files, data={'comment': 'my note'})
    assert r.status_code == 200
    d2 = r.json()['file']
    assert d2.get('original_filename') == 'note.txt'
    assert d2.get('comment') == 'my note'
    # now remove b1 (owner removes)
    r = s.post(f'/rooms/{room_id}/members/remove', headers=ra, json={'user_id': b_user['id']})
    assert r.status_code == 200
    # b1 should no longer be able to list or fetch files
    r = s.get(f'/rooms/{room_id}/files', headers=rb)
    assert r.status_code == 403


def test_dialog_attachment_metadata_and_revoked_access(client):
    s = client
    import uuid
    # register two fresh users for this test
    suffix = str(uuid.uuid4())[:8]
    a_email = f'a_{suffix}@example.com'
    b_email = f'b_{suffix}@example.com'
    r = s.post('/register', json={'email': a_email, 'username': f'a_{suffix}', 'password': 'pass'})
    assert r.status_code == 200
    a_user = r.json().get('user')
    a_tok = r.json().get('token')
    ra = {'Authorization': f'Bearer {a_tok}'}
    r = s.post('/register', json={'email': b_email, 'username': f'b_{suffix}', 'password': 'pass'})
    assert r.status_code == 200
    b_user = r.json().get('user')
    b_tok = r.json().get('token')
    rb = {'Authorization': f'Bearer {b_tok}'}

    # send friend request from a to b
    r = s.post('/friends/request', headers=ra, json={'friend_id': b_user['id']})
    assert r.status_code == 200
    # accept as b
    r = s.get('/friends/requests', headers=rb)
    reqs = r.json().get('requests', [])
    req_id = None
    for rq in reqs:
        if rq.get('from_id') == a_user['id']:
            req_id = rq['id']
            break
    assert req_id is not None
    r = s.post('/friends/requests/respond', headers=rb, json={'request_id': req_id, 'action': 'accept'})
    assert r.status_code == 200

    # upload dialog paste with comment
    data_url = 'data:text/plain;base64,' + base64.b64encode(b'hello dialog').decode()
    r = s.post(f'/dialogs/{b_user["id"]}/files/paste', headers=ra, json={'filename': 'dlg.txt', 'data': data_url, 'comment': 'dlg note'})
    assert r.status_code == 200
    f = r.json()['file']
    assert f.get('original_filename') == 'dlg.txt'
    assert f.get('comment') == 'dlg note'

    # break friendship: unfriend via API
    r = s.post('/friends/remove', headers=ra, json={'friend_id': b_user['id']})
    assert r.status_code == 200

    # now b should not be able to list or fetch the file
    r = s.get(f'/dialogs/{a_user["id"]}/files', headers=rb)
    assert r.status_code == 403
    # attempt to fetch file
    fid = f['id']
    r = s.get(f'/dialogs/{a_user["id"]}/files/{fid}', headers=rb)
    assert r.status_code == 403
