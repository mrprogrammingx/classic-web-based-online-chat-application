import uuid
import os


def _reg_and_token(client, prefix='u'):
    suffix = str(uuid.uuid4())[:8]
    email = f'{prefix}_{suffix}@example.com'
    username = f'{prefix}_{suffix}'
    r = client.post('/register', json={'email': email, 'username': username, 'password': 'pw'})
    assert r.status_code == 200
    return r.json()['user'], r.json()['token']


def test_removal_treated_as_ban_and_file_access(client, tmp_path):
    # setup users
    owner, owner_token = _reg_and_token(client, 'ownrb')
    admin, admin_token = _reg_and_token(client, 'adrb')
    victim, victim_token = _reg_and_token(client, 'victim')

    # owner creates room
    client.s.headers.update({'Authorization': f'Bearer {owner_token}'})
    rn = f"rbroom_{str(uuid.uuid4())[:8]}"
    rc = client.post('/rooms', json={'name': rn, 'description': 'ban rule test', 'visibility': 'public'})
    assert rc.status_code == 200
    rid = rc.json()['room']['id']

    # owner adds admin and victim
    assert client.post(f'/rooms/{rid}/admins/add', json={'user_id': admin['id']}).status_code == 200
    assert client.post(f'/rooms/{rid}/members/add', json={'user_id': victim['id']}).status_code == 200

    # create uploads dir and a dummy file tracked for the room
    os.makedirs('uploads', exist_ok=True)
    fname = f"file_{uuid.uuid4().hex[:8]}.txt"
    fpath = os.path.join('uploads', fname)
    with open(fpath, 'w') as f:
        f.write('secret')
    # insert room_files record directly
    import sqlite3
    from core.config import DB_PATH
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute('INSERT INTO room_files (room_id, path, created_at) VALUES (?, ?, ?)', (rid, fname, 1))
    conn.commit()
    conn.close()

    # victim posts a message before being removed
    client.s.headers.update({'Authorization': f'Bearer {victim_token}'})
    pm = client.post(f'/rooms/{rid}/messages', json={'text': 'i will be banned'})
    assert pm.status_code == 200

    # admin removes victim -> treated as ban
    client.s.headers.update({'Authorization': f'Bearer {admin_token}'})
    rem = client.post(f'/rooms/{rid}/members/remove', json={'user_id': victim['id']})
    assert rem.status_code == 200

    # victim cannot join
    client.s.headers.update({'Authorization': f'Bearer {victim_token}'})
    jr = client.post(f'/rooms/{rid}/join')
    assert jr.status_code == 403

    # victim cannot access room messages via API
    gm = client.get(f'/rooms/{rid}/messages')
    assert gm.status_code == 403

    # victim cannot access file via API
    # list files (as owner to get file id)
    client.s.headers.update({'Authorization': f'Bearer {owner_token}'})
    fl = client.get(f'/rooms/{rid}/files')
    assert fl.status_code == 200
    files = fl.json().get('files', [])
    assert files
    fid = files[0]['id']

    # victim attempts to fetch the file -> 403
    client.s.headers.update({'Authorization': f'Bearer {victim_token}'})
    gf = client.get(f'/rooms/{rid}/files/{fid}')
    assert gf.status_code == 403

    # file remains on disk until room deletion
    assert os.path.exists(fpath)
