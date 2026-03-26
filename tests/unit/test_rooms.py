import uuid


def _reg_and_token(client, prefix='user'):
    suffix = str(uuid.uuid4())[:8]
    email = f'{prefix}_{suffix}@example.com'
    username = f'{prefix}_{suffix}'
    r = client.post('/register', json={'email': email, 'username': username, 'password': 'pass'})
    assert r.status_code == 200
    return r.json()['user'], r.json()['token']


def test_room_creation_and_uniqueness(client):
    # register user
    import uuid


    def test_room_creation_and_uniqueness(client):
        # register user
        suffix = str(uuid.uuid4())[:8]
        email = f'user_{suffix}@example.com'
        username = f'user_{suffix}'
        r = client.post('/register', json={'email': email, 'username': username, 'password': 'pass'})
        assert r.status_code == 200
        token = r.json()['token']
        client.s.headers.update({'Authorization': f'Bearer {token}'})

        # create room
        rn = f"testroom_{str(uuid.uuid4())[:8]}"
        r = client.post('/rooms', json={'name': rn, 'description': 'hello'})
        assert r.status_code == 200
        room = r.json()['room']
        assert room['name'] == rn

        # duplicate name should 409
        r2 = client.post('/rooms', json={'name': rn, 'description': 'dup'})
        assert r2.status_code == 409


    def test_private_room_membership_and_admin_ban(client):
        # register owner and create private room
        suffix = str(uuid.uuid4())[:8]
        owner_email = f'owner_{suffix}@example.com'
        owner_username = f'owner_{suffix}'
        r = client.post('/register', json={'email': owner_email, 'username': owner_username, 'password': 'pass'})
        assert r.status_code == 200
        owner_token = r.json()['token']
        client.s.headers.update({'Authorization': f'Bearer {owner_token}'})

        rn = f"privroom_{str(uuid.uuid4())[:8]}"
        r = client.post('/rooms', json={'name': rn, 'visibility': 'private'})
        assert r.status_code == 200
        room = r.json()['room']
        rid = room['id']

        # register other user
        suffix2 = str(uuid.uuid4())[:8]
        other_email = f'user_{suffix2}@example.com'
        other_username = f'user_{suffix2}'
        r2 = client.post('/register', json={'email': other_email, 'username': other_username, 'password': 'pass'})
        assert r2.status_code == 200
        other_token = r2.json()['token']
        other_user_id = r2.json()['user']['id']

        # other cannot access private room
        client.s.headers.update({'Authorization': f'Bearer {other_token}'})
        rr = client.get(f'/rooms/{rid}')
        assert rr.status_code == 403

        # owner adds other as admin
        client.s.headers.update({'Authorization': f'Bearer {owner_token}'})
        add_admin = client.post(f'/rooms/{rid}/admins/add', json={'user_id': other_user_id})
        assert add_admin.status_code == 200

        # owner bans other
        ban = client.post(f'/rooms/{rid}/ban', json={'user_id': other_user_id})
        assert ban.status_code == 200

        # banned cannot join or access
        client.s.headers.update({'Authorization': f'Bearer {other_token}'})
        join = client.post(f'/rooms/{rid}/join')
        assert join.status_code == 403
        getr = client.get(f'/rooms/{rid}')
        assert getr.status_code == 403
        # other should not be able to access private room
        client.s.headers.update({'Authorization': f'Bearer {other_token}'})
        rr = client.get(f'/rooms/{rid}')
        assert rr.status_code == 403

        # switch back to owner and add other as admin
        client.s.headers.update({'Authorization': f'Bearer {owner_token}'})
        other_user_id = r2.json()['user']['id']
        add_admin = client.post(f'/rooms/{rid}/admins/add', json={'user_id': other_user_id})
        assert add_admin.status_code == 200

        # owner bans other
        ban = client.post(f'/rooms/{rid}/ban', json={'user_id': other_user_id})
        assert ban.status_code == 200

        # banned user can't join or access
        client.s.headers.update({'Authorization': f'Bearer {other_token}'})
        join = client.post(f'/rooms/{rid}/join')
        assert join.status_code == 403
        getr = client.get(f'/rooms/{rid}')
        assert getr.status_code == 403
