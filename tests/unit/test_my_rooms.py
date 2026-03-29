import uuid


def _reg_and_token(client, prefix='u'):
    suffix = str(uuid.uuid4())[:8]
    email = f'{prefix}_{suffix}@example.com'
    username = f'{prefix}_{suffix}'
    r = client.post('/register', json={'email': email, 'username': username, 'password': 'pw'})
    assert r.status_code == 200
    return r.json()['user'], r.json()['token']


def test_my_rooms_returns_only_member_rooms(client):
    """GET /rooms/mine should return only rooms the user is a member of."""
    user, token = _reg_and_token(client, 'myrooms')
    other, other_token = _reg_and_token(client, 'other')

    # other user creates a room (user is NOT a member)
    client.s.headers.update({'Authorization': f'Bearer {other_token}'})
    rn_other = f"otherroom_{uuid.uuid4().hex[:8]}"
    r = client.post('/rooms', json={'name': rn_other, 'visibility': 'public'})
    assert r.status_code == 200
    other_room_id = r.json()['room']['id']

    # user creates two rooms (owner → automatic member)
    client.s.headers.update({'Authorization': f'Bearer {token}'})
    rn1 = f"myroom1_{uuid.uuid4().hex[:8]}"
    r1 = client.post('/rooms', json={'name': rn1, 'visibility': 'public'})
    assert r1.status_code == 200
    room1_id = r1.json()['room']['id']

    rn2 = f"myroom2_{uuid.uuid4().hex[:8]}"
    r2 = client.post('/rooms', json={'name': rn2, 'visibility': 'public'})
    assert r2.status_code == 200
    room2_id = r2.json()['room']['id']

    # fetch my rooms
    res = client.get('/rooms/mine')
    assert res.status_code == 200
    data = res.json()
    assert 'rooms' in data
    my_ids = [r['id'] for r in data['rooms']]

    # user's own rooms should appear
    assert room1_id in my_ids
    assert room2_id in my_ids

    # the other user's room should NOT appear (user hasn't joined it)
    assert other_room_id not in my_ids

    # every returned room should be marked as member
    for rm in data['rooms']:
        assert rm['is_member'] is True


def test_my_rooms_updates_after_join(client):
    """After joining another user's room, /rooms/mine should include it."""
    user, token = _reg_and_token(client, 'joiner')
    owner, owner_token = _reg_and_token(client, 'roomown')

    # owner creates a room
    client.s.headers.update({'Authorization': f'Bearer {owner_token}'})
    rn = f"joinable_{uuid.uuid4().hex[:8]}"
    r = client.post('/rooms', json={'name': rn, 'visibility': 'public'})
    assert r.status_code == 200
    room_id = r.json()['room']['id']

    # user checks my rooms — room not present yet
    client.s.headers.update({'Authorization': f'Bearer {token}'})
    res = client.get('/rooms/mine')
    assert res.status_code == 200
    ids_before = [rm['id'] for rm in res.json()['rooms']]
    assert room_id not in ids_before

    # user joins the room
    jr = client.post(f'/rooms/{room_id}/join')
    assert jr.status_code == 200

    # now my rooms should include it
    res2 = client.get('/rooms/mine')
    assert res2.status_code == 200
    ids_after = [rm['id'] for rm in res2.json()['rooms']]
    assert room_id in ids_after
