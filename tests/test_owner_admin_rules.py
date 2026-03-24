import uuid


def test_owner_cannot_be_removed_or_banned(client):
    # register owner
    suffix = str(uuid.uuid4())[:8]
    owner_email = f'owner_{suffix}@example.com'
    owner_username = f'owner_{suffix}'
    r = client.post('/register', json={'email': owner_email, 'username': owner_username, 'password': 'pw'})
    assert r.status_code == 200
    owner = r.json()['user']
    owner_token = r.json()['token']

    # register admin user
    suffix2 = str(uuid.uuid4())[:8]
    admin_email = f'admin_{suffix2}@example.com'
    admin_username = f'admin_{suffix2}'
    r2 = client.post('/register', json={'email': admin_email, 'username': admin_username, 'password': 'pw'})
    assert r2.status_code == 200
    admin = r2.json()['user']
    admin_token = r2.json()['token']

    # create room as owner
    client.s.headers.update({'Authorization': f'Bearer {owner_token}'})
    rn = f"ownerroom_{str(uuid.uuid4())[:8]}"
    rc = client.post('/rooms', json={'name': rn, 'description': 'x', 'visibility': 'public'})
    assert rc.status_code == 200
    room = rc.json()['room']
    rid = room['id']

    # owner adds admin
    add = client.post(f'/rooms/{rid}/admins/add', json={'user_id': admin['id']})
    assert add.status_code == 200

    # admin tries to remove owner -> should be forbidden
    client.s.headers.update({'Authorization': f'Bearer {admin_token}'})
    rem = client.post(f'/rooms/{rid}/admins/remove', json={'user_id': owner['id']})
    assert rem.status_code == 403

    # admin tries to ban owner -> should be forbidden
    ban = client.post(f'/rooms/{rid}/ban', json={'user_id': owner['id']})
    assert ban.status_code == 403

    # owner should still be admin
    client.s.headers.update({'Authorization': f'Bearer {owner_token}'})
    got = client.get(f'/rooms/{rid}')
    assert got.status_code == 200
    roominfo = got.json()['room']
    # admins are returned as a list of user IDs
    assert owner['id'] in roominfo.get('admins', [])
