import uuid


def _reg_and_token(client, prefix='u'):
    suffix = str(uuid.uuid4())[:8]
    email = f'{prefix}_{suffix}@example.com'
    username = f'{prefix}_{suffix}'
    r = client.post('/register', json={'email': email, 'username': username, 'password': 'pw'})
    assert r.status_code == 200
    return r.json()['user'], r.json()['token']


def test_invite_requires_invitee_id(client):
    owner, owner_token = _reg_and_token(client, 'reqown')
    other, other_token = _reg_and_token(client, 'reqother')

    client.s.headers.update({'Authorization': f'Bearer {owner_token}'})
    rn = f"reqroom_{str(uuid.uuid4())[:8]}"
    rc = client.post('/rooms', json={'name': rn, 'visibility': 'private'})
    assert rc.status_code == 200
    rid = rc.json()['room']['id']

    # missing invitee_id should return 400
    r = client.post(f'/rooms/{rid}/invite', json={})
    assert r.status_code == 400


def test_invite_only_for_private_rooms(client):
    owner, owner_token = _reg_and_token(client, 'pubown')
    invitee, inv_token = _reg_and_token(client, 'pubinv')

    client.s.headers.update({'Authorization': f'Bearer {owner_token}'})
    rn = f"pubroom_{str(uuid.uuid4())[:8]}"
    # create a public room
    rc = client.post('/rooms', json={'name': rn, 'visibility': 'public'})
    assert rc.status_code == 200
    rid = rc.json()['room']['id']

    # attempting to invite to a public room should return 400
    r = client.post(f'/rooms/{rid}/invite', json={'invitee_id': invitee['id']})
    assert r.status_code == 400


def test_non_admin_cannot_invite(client):
    owner, owner_token = _reg_and_token(client, 'naown')
    nonadmin, na_token = _reg_and_token(client, 'nonadm')
    target, t_token = _reg_and_token(client, 'target')

    client.s.headers.update({'Authorization': f'Bearer {owner_token}'})
    rn = f"naroom_{str(uuid.uuid4())[:8]}"
    rc = client.post('/rooms', json={'name': rn, 'visibility': 'private'})
    assert rc.status_code == 200
    rid = rc.json()['room']['id']

    # non-admin tries to invite -> 403
    client.s.headers.update({'Authorization': f'Bearer {na_token}'})
    r = client.post(f'/rooms/{rid}/invite', json={'invitee_id': target['id']})
    assert r.status_code == 403


def test_duplicate_invite_is_idempotent(client):
    owner, owner_token = _reg_and_token(client, 'dupown')
    alice, a_token = _reg_and_token(client, 'dupalice')

    client.s.headers.update({'Authorization': f'Bearer {owner_token}'})
    rn = f"duproom_{str(uuid.uuid4())[:8]}"
    rc = client.post('/rooms', json={'name': rn, 'visibility': 'private'})
    assert rc.status_code == 200
    rid = rc.json()['room']['id']

    # invite twice; server uses INSERT OR IGNORE so both calls should return ok
    r1 = client.post(f'/rooms/{rid}/invite', json={'invitee_id': alice['id']})
    r2 = client.post(f'/rooms/{rid}/invite', json={'invitee_id': alice['id']})
    assert r1.status_code == 200
    assert r2.status_code == 200

    # owner should see only one invite record for that invitee
    client.s.headers.update({'Authorization': f'Bearer {owner_token}'})
    li = client.get(f'/rooms/{rid}/invites')
    assert li.status_code == 200
    invites = li.json().get('invites', [])
    # count invites targeting alice
    alice_invites = [i for i in invites if i.get('invitee_id') == alice['id']]
    assert len(alice_invites) == 1
