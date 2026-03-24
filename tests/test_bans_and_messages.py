import uuid


def _reg_and_token(client, prefix='u'):
    suffix = str(uuid.uuid4())[:8]
    email = f'{prefix}_{suffix}@example.com'
    username = f'{prefix}_{suffix}'
    r = client.post('/register', json={'email': email, 'username': username, 'password': 'pw'})
    assert r.status_code == 200
    return r.json()['user'], r.json()['token']


def test_bans_listing_and_unban(client):
    # owner, admin, and member
    owner, owner_token = _reg_and_token(client, 'own')
    admin, admin_token = _reg_and_token(client, 'adm')
    member, member_token = _reg_and_token(client, 'mem')

    # owner creates a public room
    client.s.headers.update({'Authorization': f'Bearer {owner_token}'})
    rn = f"banroom_{str(uuid.uuid4())[:8]}"
    rc = client.post('/rooms', json={'name': rn, 'description': 'ban test', 'visibility': 'public'})
    assert rc.status_code == 200
    room = rc.json()['room']
    rid = room['id']

    # owner adds admin and member
    a = client.post(f'/rooms/{rid}/admins/add', json={'user_id': admin['id']})
    assert a.status_code == 200
    am = client.post(f'/rooms/{rid}/members/add', json={'user_id': member['id']})
    assert am.status_code == 200

    # admin bans member
    client.s.headers.update({'Authorization': f'Bearer {admin_token}'})
    ban = client.post(f'/rooms/{rid}/ban', json={'user_id': member['id']})
    assert ban.status_code == 200

    # admin and owner can list bans, and banner_id should be admin
    bres = client.get(f'/rooms/{rid}/bans')
    assert bres.status_code == 200
    bans = bres.json().get('bans', [])
    assert any(b['banned_id'] == member['id'] and b['banner_id'] == admin['id'] for b in bans)

    client.s.headers.update({'Authorization': f'Bearer {owner_token}'})
    bres2 = client.get(f'/rooms/{rid}/bans')
    assert bres2.status_code == 200

    # banned member cannot join
    client.s.headers.update({'Authorization': f'Bearer {member_token}'})
    join = client.post(f'/rooms/{rid}/join')
    assert join.status_code == 403

    # admin unbans member
    client.s.headers.update({'Authorization': f'Bearer {admin_token}'})
    un = client.post(f'/rooms/{rid}/unban', json={'user_id': member['id']})
    assert un.status_code == 200

    # member can now join
    client.s.headers.update({'Authorization': f'Bearer {member_token}'})
    j2 = client.post(f'/rooms/{rid}/join')
    assert j2.status_code == 200


def test_member_removal_and_message_deletion(client):
    # owner, admin, member
    owner, owner_token = _reg_and_token(client, 'own2')
    admin, admin_token = _reg_and_token(client, 'adm2')
    member, member_token = _reg_and_token(client, 'mem2')

    # owner creates room
    client.s.headers.update({'Authorization': f'Bearer {owner_token}'})
    rn = f"msgroom_{str(uuid.uuid4())[:8]}"
    rc = client.post('/rooms', json={'name': rn, 'description': 'msg test', 'visibility': 'public'})
    assert rc.status_code == 200
    rid = rc.json()['room']['id']

    # owner adds admin and member
    addadm = client.post(f'/rooms/{rid}/admins/add', json={'user_id': admin['id']})
    assert addadm.status_code == 200
    addm = client.post(f'/rooms/{rid}/members/add', json={'user_id': member['id']})
    assert addm.status_code == 200

    # member posts a message
    client.s.headers.update({'Authorization': f'Bearer {member_token}'})
    pm = client.post(f'/rooms/{rid}/messages', json={'text': 'hello world'})
    assert pm.status_code == 200
    mid = pm.json()['message']['id']

    # admin deletes the message
    client.s.headers.update({'Authorization': f'Bearer {admin_token}'})
    resp = client.s.delete(client.s.base_url + f'/rooms/{rid}/messages/{mid}')
    assert resp.status_code == 200

    # message no longer present
    client.s.headers.update({'Authorization': f'Bearer {member_token}'})
    lm = client.get(f'/rooms/{rid}/messages')
    assert lm.status_code == 200
    msgs = lm.json().get('messages', [])
    assert all(m.get('text') != 'hello world' for m in msgs)

    # admin removes member
    client.s.headers.update({'Authorization': f'Bearer {admin_token}'})
    rem = client.post(f'/rooms/{rid}/members/remove', json={'user_id': member['id']})
    assert rem.status_code == 200

    # member should no longer be in members list
    client.s.headers.update({'Authorization': f'Bearer {owner_token}'})
    got = client.get(f'/rooms/{rid}')
    assert got.status_code == 200
    info = got.json()['room']
    assert member['id'] not in info.get('members', [])

    # owner may remove admin
    client.s.headers.update({'Authorization': f'Bearer {owner_token}'})
    remadm = client.post(f'/rooms/{rid}/admins/remove', json={'user_id': admin['id']})
    assert remadm.status_code == 200


def test_non_admin_cannot_call_admin_endpoints(client):
    # owner, non_admin, target, admin
    owner, owner_token = _reg_and_token(client, 'ownx')
    nonadm, nonadm_token = _reg_and_token(client, 'nonadm')
    target, target_token = _reg_and_token(client, 'tgtx')
    admin, admin_token = _reg_and_token(client, 'admx')

    # owner creates room
    client.s.headers.update({'Authorization': f'Bearer {owner_token}'})
    rn = f"negroom_{str(uuid.uuid4())[:8]}"
    rc = client.post('/rooms', json={'name': rn, 'description': 'neg test', 'visibility': 'public'})
    assert rc.status_code == 200
    rid = rc.json()['room']['id']

    # owner adds admin, non-admin and target as members
    assert client.post(f'/rooms/{rid}/admins/add', json={'user_id': admin['id']}).status_code == 200
    assert client.post(f'/rooms/{rid}/members/add', json={'user_id': nonadm['id']}).status_code == 200
    assert client.post(f'/rooms/{rid}/members/add', json={'user_id': target['id']}).status_code == 200

    # target posts a message
    client.s.headers.update({'Authorization': f'Bearer {target_token}'})
    pm = client.post(f'/rooms/{rid}/messages', json={'text': 'to be deleted'})
    assert pm.status_code == 200
    mid = pm.json()['message']['id']

    # non-admin attempts admin actions -> all should be 403
    client.s.headers.update({'Authorization': f'Bearer {nonadm_token}'})
    r1 = client.post(f'/rooms/{rid}/ban', json={'user_id': target['id']})
    assert r1.status_code == 403
    r2 = client.get(f'/rooms/{rid}/bans')
    assert r2.status_code == 403
    r3 = client.post(f'/rooms/{rid}/unban', json={'user_id': target['id']})
    assert r3.status_code == 403
    r4 = client.post(f'/rooms/{rid}/members/remove', json={'user_id': target['id']})
    assert r4.status_code == 403
    # delete message using direct session delete
    resp = client.s.delete(client.s.base_url + f'/rooms/{rid}/messages/{mid}')
    assert resp.status_code == 403

    # non-admin tries to remove admin -> forbidden
    r5 = client.post(f'/rooms/{rid}/admins/remove', json={'user_id': admin['id']})
    assert r5.status_code == 403
