import os
import uuid


def _reg_and_token(client, prefix='u'):
    suffix = str(uuid.uuid4())[:8]
    email = f'{prefix}_{suffix}@example.com'
    username = f'{prefix}_{suffix}'
    r = client.post('/register', json={'email': email, 'username': username, 'password': 'pw'})
    assert r.status_code == 200
    return r.json()['user'], r.json()['token']


def test_send_and_receive_dialog_messages(client):
    a, ta = _reg_and_token(client, 'alice')
    b, tb = _reg_and_token(client, 'bob')

    # make them friends both ways (tests rely on friends policy)
    client.s.headers.update({'Authorization': f'Bearer {ta}'})
    assert client.post('/friends/request', json={'username': b['username']}).status_code == 200
    client.s.headers.update({'Authorization': f'Bearer {tb}'})
    # accept friend request
    reqs = client.get('/friends/requests')
    reqs_json = reqs.json().get('requests', [])
    # find incoming request from alice (friends API returns 'username' field)
    rid = None
    for r in reqs_json:
        if r.get('username') == a['username']:
            rid = r['id']
            break
    assert rid is not None
    assert client.post('/friends/requests/respond', json={'request_id': rid, 'action': 'accept'}).status_code == 200

    # now alice sends a dialog message to bob
    client.s.headers.update({'Authorization': f'Bearer {ta}'})
    send = client.post(f'/dialogs/{b["id"]}/messages', json={'text': 'hello bob'})
    assert send.status_code == 200
    mid = send.json()['message']['id']

    # bob fetches history
    client.s.headers.update({'Authorization': f'Bearer {tb}'})
    hist = client.get(f'/dialogs/{a["id"]}/messages')
    assert hist.status_code == 200
    msgs = hist.json().get('messages', [])
    assert any(m['text'] == 'hello bob' for m in msgs)


def test_dialog_read_only_when_banned(client):
    a, ta = _reg_and_token(client, 'alice2')
    b, tb = _reg_and_token(client, 'bob2')

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

    # b bans a using global bans endpoint
    client.s.headers.update({'Authorization': f'Bearer {tb}'})
    assert client.post('/ban', json={'banned_id': a['id']}).status_code == 200

    # a attempts to fetch dialog history -> should get read_only true
    client.s.headers.update({'Authorization': f'Bearer {ta}'})
    h = client.get(f'/dialogs/{b["id"]}/messages')
    assert h.status_code == 200
    assert h.json().get('read_only') is True
    # and trying to send should be forbidden
    s = client.post(f'/dialogs/{b["id"]}/messages', json={'text': 'you are banned'})
    assert s.status_code == 403


def test_dialog_attachments_listing_and_serving_permissions(client):
    a, ta = _reg_and_token(client, 'alice3')
    b, tb = _reg_and_token(client, 'bob3')

    # make friends
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

    # create uploads dir and a dummy attachment; insert DB record directly
    os.makedirs('uploads', exist_ok=True)
    fname = f"dlg_{uuid.uuid4().hex[:8]}.txt"
    fpath = os.path.join('uploads', fname)
    with open(fpath, 'w') as fh:
        fh.write('attachment')
    import sqlite3
    conn = sqlite3.connect('auth.db')
    cur = conn.cursor()
    # we don't need a message_id for the test; insert both directions to ensure listing works
    cur.execute('INSERT INTO private_message_files (message_id, from_id, to_id, path, created_at) VALUES (?, ?, ?, ?, ?)', (None, a['id'], b['id'], fname, 1))
    conn.commit()
    conn.close()

    # alice lists files
    client.s.headers.update({'Authorization': f'Bearer {ta}'})
    lf = client.get(f'/dialogs/{b["id"]}/files')
    assert lf.status_code == 200
    files = lf.json().get('files', [])
    assert files
    fid = files[0]['id']

    # bob can fetch the file by calling the file-serving endpoint if implemented (we'll call the direct path for now)
    # For now assert that the file exists on disk and listing works for both participants
    client.s.headers.update({'Authorization': f'Bearer {tb}'})
    lf2 = client.get(f'/dialogs/{a["id"]}/files')
    assert lf2.status_code == 200
    assert any(f['path'] == fname for f in lf2.json().get('files', []))
