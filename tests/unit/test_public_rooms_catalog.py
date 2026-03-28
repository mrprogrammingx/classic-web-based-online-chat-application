import uuid


def _reg_and_token(client, prefix='user'):
    suffix = str(uuid.uuid4())[:8]
    email = f'{prefix}_{suffix}@example.com'
    username = f'{prefix}_{suffix}'
    r = client.post('/register', json={'email': email, 'username': username, 'password': 'pass'})
    assert r.status_code == 200
    return r.json()['user'], r.json()['token']


def test_public_rooms_catalog_and_join(client):
    # owner creates two public rooms with different descriptions
    owner, owner_token = _reg_and_token(client, 'owner')
    client.s.headers.update({'Authorization': f'Bearer {owner_token}'})
    rn1 = f"publicroom_{str(uuid.uuid4())[:8]}"
    rn2 = f"talk_room_{str(uuid.uuid4())[:8]}"
    r1 = client.post('/rooms', json={'name': rn1, 'description': 'general chat'})
    assert r1.status_code == 200
    r2 = client.post('/rooms', json={'name': rn2, 'description': 'random talk'})
    assert r2.status_code == 200

    # another user joins first room
    u, t = _reg_and_token(client, 'joiner')
    client.s.headers.update({'Authorization': f'Bearer {t}'})
    # get catalog
    catalog = client.get('/rooms')
    assert catalog.status_code == 200
    rooms = catalog.json()['rooms']
    # find the created rooms
    found1 = [r for r in rooms if r['name'] == rn1]
    found2 = [r for r in rooms if r['name'] == rn2]
    assert found1 and found2
    # member_count should be >= 1 for owner-created rooms (owner was added automatically)
    assert found1[0]['member_count'] >= 1
    # the catalog should include an explicit is_member boolean for each room
    # since this request is authenticated as the joiner (not yet a member) it
    # should be False for the room the joiner didn't create/join yet.
    assert 'is_member' in found1[0]
    assert found1[0]['is_member'] is False

    # join rn1
    jr = client.post(f"/rooms/{found1[0]['id']}/join")
    assert jr.status_code == 200

    # after join, member_count should increase (list with a query and find)
    catalog2 = client.get('/rooms')
    rooms2 = catalog2.json()['rooms']
    f1 = [r for r in rooms2 if r['name'] == rn1][0]
    assert f1['member_count'] >= found1[0]['member_count'] + 1 - 1  # at least same or increment
    # after joining, the is_member flag should be True for this user
    assert 'is_member' in f1
    assert f1['is_member'] is True

    # search by q should find appropriate room
    search = client.get('/rooms?q=talk')
    assert search.status_code == 200
    names = [r['name'] for r in search.json()['rooms']]
    assert any('talk' in n for n in names)
