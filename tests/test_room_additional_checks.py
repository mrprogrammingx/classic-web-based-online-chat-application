import os
import uuid


def _reg_and_token(client, prefix='u'):
    suffix = str(uuid.uuid4())[:8]
    email = f'{prefix}_{suffix}@example.com'
    username = f'{prefix}_{suffix}'
    r = client.post('/register', json={'email': email, 'username': username, 'password': 'pw'})
    assert r.status_code == 200
    return r.json()['user'], r.json()['token']


def test_non_admin_cannot_invite(client):
    owner, owner_token = _reg_and_token(client, 'o_inv')
    nonadm, nonadm_token = _reg_and_token(client, 'n_inv')
    target, target_token = _reg_and_token(client, 't_inv')

    # owner creates private room
    client.s.headers.update({'Authorization': f'Bearer {owner_token}'})
    rn = f"prv_{str(uuid.uuid4())[:8]}"
    rc = client.post('/rooms', json={'name': rn, 'visibility': 'private'})
    assert rc.status_code == 200
    rid = rc.json()['room']['id']

    # non-admin attempts to invite -> 403
    client.s.headers.update({'Authorization': f'Bearer {nonadm_token}'})
    r = client.post(f'/rooms/{rid}/invite', json={'invitee_id': target['id']})
    assert r.status_code == 403


def test_file_serving_permissions(client):
    owner, owner_token = _reg_and_token(client, 'o_file')
    member, member_token = _reg_and_token(client, 'm_file')
    outsider, outsider_token = _reg_and_token(client, 'out_file')

    # owner creates private room and adds member
    client.s.headers.update({'Authorization': f'Bearer {owner_token}'})
    rn = f"fileprv_{str(uuid.uuid4())[:8]}"
    rc = client.post('/rooms', json={'name': rn, 'visibility': 'private'})
    assert rc.status_code == 200
    rid = rc.json()['room']['id']
    assert client.post(f'/rooms/{rid}/members/add', json={'user_id': member['id']}).status_code == 200

    # create uploads dir and a dummy file tracked for the room
    os.makedirs('uploads', exist_ok=True)
    fname = f"file_{uuid.uuid4().hex[:8]}.txt"
    fpath = os.path.join('uploads', fname)
    with open(fpath, 'w') as f:
        f.write('private secret')
    import sqlite3
    conn = sqlite3.connect('auth.db')
    cur = conn.cursor()
    cur.execute('INSERT INTO room_files (room_id, path, created_at) VALUES (?, ?, ?)', (rid, fname, 1))
    conn.commit()
    conn.close()

    # member can fetch the file
    client.s.headers.update({'Authorization': f'Bearer {member_token}'})
    fl = client.get(f'/rooms/{rid}/files')
    assert fl.status_code == 200
    files = fl.json().get('files', [])
    assert files
    fid = files[0]['id']
    gf = client.s.get(client.s.base_url + f'/rooms/{rid}/files/{fid}')
    assert gf.status_code == 200

    # outsider cannot fetch private room file
    client.s.headers.update({'Authorization': f'Bearer {outsider_token}'})
    gf2 = client.s.get(client.s.base_url + f'/rooms/{rid}/files/{fid}')
    assert gf2.status_code == 403

    # make room public and outsider may fetch
    client.s.headers.update({'Authorization': f'Bearer {owner_token}'})
    # directly flip visibility in DB for test simplicity
    import sqlite3 as _sqlite
    conn = _sqlite.connect('auth.db')
    cur = conn.cursor()
    cur.execute("UPDATE rooms SET visibility = 'public' WHERE id = ?", (rid,))
    conn.commit()
    conn.close()

    client.s.headers.update({'Authorization': f'Bearer {outsider_token}'})
    gf3 = client.s.get(client.s.base_url + f'/rooms/{rid}/files/{fid}')
    assert gf3.status_code == 200

    # ban member and ensure they can no longer fetch
    client.s.headers.update({'Authorization': f'Bearer {owner_token}'})
    # ban member
    b = client.post(f'/rooms/{rid}/ban', json={'user_id': member['id']})
    assert b.status_code == 200
    client.s.headers.update({'Authorization': f'Bearer {member_token}'})
    gf4 = client.s.get(client.s.base_url + f'/rooms/{rid}/files/{fid}')
    assert gf4.status_code == 403
