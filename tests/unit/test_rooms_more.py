import uuid


def _reg_and_token(client, prefix='user'):
    suffix = str(uuid.uuid4())[:8]
    email = f'{prefix}_{suffix}@example.com'
    username = f'{prefix}_{suffix}'
    r = client.post('/register', json={'email': email, 'username': username, 'password': 'pass'})
    assert r.status_code == 200
    return r.json()['user'], r.json()['token']


def test_join_leave_and_list_members(client):
    owner, owner_token = _reg_and_token(client, 'owner')
    client.s.headers.update({'Authorization': f'Bearer {owner_token}'})
    rn = f"membersroom_{str(uuid.uuid4())[:8]}"
    r = client.post('/rooms', json={'name': rn})
    assert r.status_code == 200
    room = r.json()['room']
    rid = room['id']

    # create two members
    m1, t1 = _reg_and_token(client, 'm1')
    m2, t2 = _reg_and_token(client, 'm2')

    # m1 joins public room
    client.s.headers.update({'Authorization': f'Bearer {t1}'})
    jr = client.post(f'/rooms/{rid}/join')
    assert jr.status_code == 200

    # m2 is added by owner
    client.s.headers.update({'Authorization': f'Bearer {owner_token}'})
    add = client.post(f'/rooms/{rid}/members/add', json={'user_id': m2['id']})
    assert add.status_code == 200

    # list room should include members (owner, m1, m2)
    client.s.headers.update({'Authorization': f'Bearer {owner_token}'})
    gr = client.get(f'/rooms/{rid}')
    assert gr.status_code == 200
    members = gr.json()['room']['members']
    assert owner['id'] in members
    assert m1['id'] in members
    assert m2['id'] in members

    # m1 leaves
    client.s.headers.update({'Authorization': f'Bearer {t1}'})
    leave = client.post(f'/rooms/{rid}/leave')
    assert leave.status_code == 200
    client.s.headers.update({'Authorization': f'Bearer {owner_token}'})
    gr2 = client.get(f'/rooms/{rid}')
    members2 = gr2.json()['room']['members']
    assert m1['id'] not in members2


def test_admin_removal_and_unban_and_message_permissions(client):
    owner, owner_token = _reg_and_token(client, 'own2')
    client.s.headers.update({'Authorization': f'Bearer {owner_token}'})
    rn = f"privmsgroom_{str(uuid.uuid4())[:8]}"
    # create private room
    r = client.post('/rooms', json={'name': rn, 'visibility': 'private'})
    assert r.status_code == 200
    room = r.json()['room']
    rid = room['id']

    # create user A and B
    a, ta = _reg_and_token(client, 'A')
    b, tb = _reg_and_token(client, 'B')

    # owner adds A as member and admin
    client.s.headers.update({'Authorization': f'Bearer {owner_token}'})
    addm = client.post(f'/rooms/{rid}/members/add', json={'user_id': a['id']})
    assert addm.status_code == 200
    addadm = client.post(f'/rooms/{rid}/admins/add', json={'user_id': a['id']})
    assert addadm.status_code == 200

    # A posts a message
    client.s.headers.update({'Authorization': f'Bearer {ta}'})
    pm = client.post(f'/rooms/{rid}/messages', json={'text': 'hello from A'})
    assert pm.status_code == 200

    # owner bans A
    client.s.headers.update({'Authorization': f'Bearer {owner_token}'})
    ban = client.post(f'/rooms/{rid}/ban', json={'user_id': a['id']})
    assert ban.status_code == 200

    # A cannot post or access
    client.s.headers.update({'Authorization': f'Bearer {ta}'})
    pm2 = client.post(f'/rooms/{rid}/messages', json={'text': 'should fail'})
    assert pm2.status_code == 403
    # GET /rooms/{id} now returns 200 with is_banned=True instead of 403,
    # so the client JS can render a proper ban notice instead of an opaque error.
    ga = client.get(f'/rooms/{rid}')
    assert ga.status_code == 200
    assert ga.json()['room']['is_banned'] is True

    # owner unbans A
    client.s.headers.update({'Authorization': f'Bearer {owner_token}'})
    un = client.post(f'/rooms/{rid}/unban', json={'user_id': a['id']})
    assert un.status_code == 200

    # now owner re-adds A as member (and not admin automatically)
    addm2 = client.post(f'/rooms/{rid}/members/add', json={'user_id': a['id']})
    assert addm2.status_code == 200

    # A can post again
    client.s.headers.update({'Authorization': f'Bearer {ta}'})
    pm3 = client.post(f'/rooms/{rid}/messages', json={'text': 'i am back'})
    assert pm3.status_code == 200

    # owner removes admin status from A (even though A was re-added without admin)
    client.s.headers.update({'Authorization': f'Bearer {owner_token}'})
    rem = client.post(f'/rooms/{rid}/admins/remove', json={'user_id': a['id']})
    assert rem.status_code == 200
