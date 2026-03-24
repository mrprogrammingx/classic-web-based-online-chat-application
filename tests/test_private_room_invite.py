import uuid


def _reg_and_token(client, prefix='user'):
    suffix = str(uuid.uuid4())[:8]
    email = f'{prefix}_{suffix}@example.com'
    username = f'{prefix}_{suffix}'
    r = client.post('/register', json={'email': email, 'username': username, 'password': 'pass'})
    assert r.status_code == 200
    return r.json()['user'], r.json()['token']


def test_private_room_invitation_only(client):
    owner, owner_token = _reg_and_token(client, 'owner')
    client.s.headers.update({'Authorization': f'Bearer {owner_token}'})
    rn = f"private_invite_{str(uuid.uuid4())[:8]}"
    r = client.post('/rooms', json={'name': rn, 'visibility': 'private', 'description': 'secret room'})
    assert r.status_code == 200
    room = r.json()['room']
    rid = room['id']

    # the private room should not appear in the public catalog
    client.s.headers.update({'Authorization': f'Bearer {owner_token}'})
    catalog = client.get('/rooms')
    assert catalog.status_code == 200
    assert not any(r['id'] == rid for r in catalog.json()['rooms'])

    # another user cannot join by themselves
    u, t = _reg_and_token(client, 'intruder')
    client.s.headers.update({'Authorization': f'Bearer {t}'})
    jr = client.post(f'/rooms/{rid}/join')
    assert jr.status_code == 403

    # owner invites/adds the user
    client.s.headers.update({'Authorization': f'Bearer {owner_token}'})
    add = client.post(f'/rooms/{rid}/members/add', json={'user_id': u['id']})
    assert add.status_code == 200

    # now the user can access the room
    client.s.headers.update({'Authorization': f'Bearer {t}'})
    getr = client.get(f'/rooms/{rid}')
    assert getr.status_code == 200
    # ensure membership is reflected
    members = client.get(f'/rooms/{rid}').json()['room']['members']
    assert u['id'] in members
