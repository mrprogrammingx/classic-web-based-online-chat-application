import uuid


def _reg_and_token(client, prefix='u'):
    suffix = str(uuid.uuid4())[:8]
    email = f'{prefix}_{suffix}@example.com'
    username = f'{prefix}_{suffix}'
    r = client.post('/register', json={'email': email, 'username': username, 'password': 'pw'})
    assert r.status_code == 200
    return r.json()['user'], r.json()['token']


def test_invite_flow(client):
    owner, owner_token = _reg_and_token(client, 'invown')
    alice, a_token = _reg_and_token(client, 'alice')
    bob, b_token = _reg_and_token(client, 'bob')

    # owner creates a private room
    client.s.headers.update({'Authorization': f'Bearer {owner_token}'})
    rn = f"invroom_{str(uuid.uuid4())[:8]}"
    rc = client.post('/rooms', json={'name': rn, 'visibility': 'private'})
    assert rc.status_code == 200
    rid = rc.json()['room']['id']

    # owner invites alice
    inv = client.post(f'/rooms/{rid}/invite', json={'invitee_id': alice['id']})
    assert inv.status_code == 200

    # alice lists her invites
    client.s.headers.update({'Authorization': f'Bearer {a_token}'})
    li = client.get(f'/rooms/{rid}/invites')
    # since alice is invitee, listing the room invites for her returns invites
    assert li.status_code == 200
    invites = li.json().get('invites', [])
    assert invites
    iid = invites[0]['id']

    # alice accepts
    acc = client.post(f'/rooms/{rid}/invites/{iid}/accept')
    assert acc.status_code == 200

    # alice should now be a member
    got = client.get(f'/rooms/{rid}')
    assert got.status_code == 200
    members = got.json()['room'].get('members', [])
    assert alice['id'] in members

    # owner invites bob, then bob declines
    client.s.headers.update({'Authorization': f'Bearer {owner_token}'})
    inv2 = client.post(f'/rooms/{rid}/invite', json={'invitee_id': bob['id']})
    assert inv2.status_code == 200
    client.s.headers.update({'Authorization': f'Bearer {b_token}'})
    lb = client.get(f'/rooms/{rid}/invites')
    assert lb.status_code == 200
    bids = lb.json().get('invites', [])
    assert bids
    bid = bids[0]['id']
    dec = client.post(f'/rooms/{rid}/invites/{bid}/decline')
    assert dec.status_code == 200


def test_banned_user_cannot_accept_invite(client):
    owner, owner_token = _reg_and_token(client, 'inv2own')
    admin, admin_token = _reg_and_token(client, 'inv2adm')
    victim, vic_token = _reg_and_token(client, 'inv2vic')

    # create private room
    client.s.headers.update({'Authorization': f'Bearer {owner_token}'})
    rn = f"invroom2_{str(uuid.uuid4())[:8]}"
    rc = client.post('/rooms', json={'name': rn, 'visibility': 'private'})
    assert rc.status_code == 200
    rid = rc.json()['room']['id']

    # owner adds admin
    assert client.post(f'/rooms/{rid}/admins/add', json={'user_id': admin['id']}).status_code == 200

    # admin bans victim
    client.s.headers.update({'Authorization': f'Bearer {admin_token}'})
    b = client.post(f'/rooms/{rid}/ban', json={'user_id': victim['id']})
    assert b.status_code == 200

    # owner attempts to invite victim
    client.s.headers.update({'Authorization': f'Bearer {owner_token}'})
    inv = client.post(f'/rooms/{rid}/invite', json={'invitee_id': victim['id']})
    # invitation may be created at DB level, but acceptance should fail due to ban
    assert inv.status_code == 200

    # list invite id
    client.s.headers.update({'Authorization': f'Bearer {vic_token}'})
    li = client.get(f'/rooms/{rid}/invites')
    assert li.status_code == 200
    invites = li.json().get('invites', [])
    # find the invite id in whichever listing includes it
    iid = None
    for inv in invites:
        if inv.get('room_id') == rid or inv.get('id'):
            iid = inv.get('id') or inv.get('id')
            break
    if iid is None:
        client.s.headers.update({'Authorization': f'Bearer {owner_token}'})
        rli = client.get(f'/rooms/{rid}/invites')
        invites2 = rli.json().get('invites', [])
        for inv in invites2:
            if inv.get('invitee_id') == victim['id']:
                iid = inv['id']
                break
    assert iid is not None

    # victim attempts to accept -> should be 403
    client.s.headers.update({'Authorization': f'Bearer {vic_token}'})
    acc = client.post(f'/rooms/{rid}/invites/{iid}/accept')
    assert acc.status_code == 403


def test_invitations_mine_endpoint(client):
    """GET /invitations/mine returns enriched pending invitations for the logged-in user."""
    owner, owner_token = _reg_and_token(client, 'mineown')
    invitee, inv_token = _reg_and_token(client, 'mineinv')

    # create a private room
    client.s.headers.update({'Authorization': f'Bearer {owner_token}'})
    rn = f"mineroom_{str(uuid.uuid4())[:8]}"
    rc = client.post('/rooms', json={'name': rn, 'visibility': 'private'})
    assert rc.status_code == 200
    rid = rc.json()['room']['id']

    # invite the user
    inv = client.post(f'/rooms/{rid}/invite', json={'invitee_id': invitee['id']})
    assert inv.status_code == 200

    # invitee calls /invitations/mine — should see the pending invite with room_name
    client.s.headers.update({'Authorization': f'Bearer {inv_token}'})
    resp = client.get('/invitations/mine')
    assert resp.status_code == 200
    invites = resp.json().get('invites', [])
    assert any(i['room_id'] == rid for i in invites), "Pending invite should appear in /invitations/mine"
    matching = [i for i in invites if i['room_id'] == rid][0]
    assert matching.get('room_name') == rn, "room_name should be included in the response"
    iid = matching['id']

    # accept the invite via the room-specific endpoint
    accepted = client.post(f'/rooms/{rid}/invites/{iid}/accept')
    assert accepted.status_code == 200

    # /invitations/mine should no longer list it
    resp2 = client.get('/invitations/mine')
    assert resp2.status_code == 200
    invites2 = resp2.json().get('invites', [])
    assert not any(i['room_id'] == rid for i in invites2), "Accepted invite should no longer appear in /invitations/mine"


def test_invitations_mine_decline(client):
    """Declining an invite removes it from /invitations/mine."""
    owner, owner_token = _reg_and_token(client, 'decown')
    invitee, inv_token = _reg_and_token(client, 'decinv')

    client.s.headers.update({'Authorization': f'Bearer {owner_token}'})
    rn = f"decroom_{str(uuid.uuid4())[:8]}"
    rc = client.post('/rooms', json={'name': rn, 'visibility': 'private'})
    assert rc.status_code == 200
    rid = rc.json()['room']['id']

    client.post(f'/rooms/{rid}/invite', json={'invitee_id': invitee['id']})

    client.s.headers.update({'Authorization': f'Bearer {inv_token}'})
    resp = client.get('/invitations/mine')
    invites = resp.json().get('invites', [])
    matching = [i for i in invites if i['room_id'] == rid]
    assert matching
    iid = matching[0]['id']

    dec = client.post(f'/rooms/{rid}/invites/{iid}/decline')
    assert dec.status_code == 200

    resp2 = client.get('/invitations/mine')
    invites2 = resp2.json().get('invites', [])
    assert not any(i['room_id'] == rid for i in invites2)
