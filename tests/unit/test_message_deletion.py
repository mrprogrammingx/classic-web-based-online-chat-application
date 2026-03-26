import uuid


def _reg_and_token(client, prefix='u'):
    suffix = str(uuid.uuid4())[:8]
    email = f'{prefix}_{suffix}@example.com'
    username = f'{prefix}_{suffix}'
    r = client.post('/register', json={'email': email, 'username': username, 'password': 'pw'})
    assert r.status_code == 200
    return r.json()['user'], r.json()['token']


def test_author_can_delete_message(client):
    owner, ot = _reg_and_token(client, 'own_del')
    user, ut = _reg_and_token(client, 'auth_del')

    client.s.headers.update({'Authorization': f'Bearer {ot}'})
    rn = f"delroom_{uuid.uuid4().hex[:8]}"
    rc = client.post('/rooms', json={'name': rn, 'visibility': 'public'})
    rid = rc.json()['room']['id']
    client.post(f'/rooms/{rid}/members/add', json={'user_id': user['id']})

    client.s.headers.update({'Authorization': f'Bearer {ut}'})
    p = client.post(f'/rooms/{rid}/messages', json={'text': 'to be deleted'})
    mid = p.json()['message']['id']

    # author deletes
    d = client.delete(f'/rooms/{rid}/messages/{mid}')
    assert d.status_code == 200


def test_admin_can_delete_message(client):
    owner, ot = _reg_and_token(client, 'own_del2')
    user, ut = _reg_and_token(client, 'u_del2')
    admin, at = _reg_and_token(client, 'admin_del')

    client.s.headers.update({'Authorization': f'Bearer {ot}'})
    rn = f"delroom2_{uuid.uuid4().hex[:8]}"
    rc = client.post('/rooms', json={'name': rn, 'visibility': 'public'})
    rid = rc.json()['room']['id']
    # add user and admin
    client.post(f'/rooms/{rid}/members/add', json={'user_id': user['id']})
    client.post(f'/rooms/{rid}/members/add', json={'user_id': admin['id']})
    # make admin an admin
    client.post(f'/rooms/{rid}/admins/add', json={'user_id': admin['id']})

    client.s.headers.update({'Authorization': f'Bearer {ut}'})
    p = client.post(f'/rooms/{rid}/messages', json={'text': 'admin delete me'})
    mid = p.json()['message']['id']

    client.s.headers.update({'Authorization': f'Bearer {at}'})
    d = client.delete(f'/rooms/{rid}/messages/{mid}')
    assert d.status_code == 200


def test_non_author_non_admin_cannot_delete(client):
    owner, ot = _reg_and_token(client, 'own_del3')
    user, ut = _reg_and_token(client, 'u_del3')
    other, ot2 = _reg_and_token(client, 'other_del')

    client.s.headers.update({'Authorization': f'Bearer {ot}'})
    rn = f"delroom3_{uuid.uuid4().hex[:8]}"
    rc = client.post('/rooms', json={'name': rn, 'visibility': 'public'})
    rid = rc.json()['room']['id']
    client.post(f'/rooms/{rid}/members/add', json={'user_id': user['id']})
    client.post(f'/rooms/{rid}/members/add', json={'user_id': other['id']})

    client.s.headers.update({'Authorization': f'Bearer {ut}'})
    p = client.post(f'/rooms/{rid}/messages', json={'text': 'safe message'})
    mid = p.json()['message']['id']

    client.s.headers.update({'Authorization': f'Bearer {ot2}'})
    d = client.delete(f'/rooms/{rid}/messages/{mid}')
    assert d.status_code == 403
