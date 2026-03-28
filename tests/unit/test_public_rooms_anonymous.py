import uuid


def _reg_and_token(client, prefix='user'):
    suffix = str(uuid.uuid4())[:8]
    email = f'{prefix}_{suffix}@example.com'
    username = f'{prefix}_{suffix}'
    r = client.post('/register', json={'email': email, 'username': username, 'password': 'pass'})
    assert r.status_code == 200
    return r.json()['user'], r.json()['token']


def test_public_rooms_anonymous_view(client):
    # owner creates a public room
    owner, owner_token = _reg_and_token(client, 'owner')
    client.s.headers.update({'Authorization': f'Bearer {owner_token}'})
    rn = f"publicroom_{str(uuid.uuid4())[:8]}"
    r1 = client.post('/rooms', json={'name': rn, 'description': 'public hello', 'visibility': 'public'})
    assert r1.status_code == 200

    # clear Authorization header and cookies to simulate anonymous client
    client.s.headers.pop('Authorization', None)
    # ensure no cookies are sent by using a fresh session object
    anon = type('C', (), {})()
    anon.s = client.s.__class__()
    anon.base = client.s.base_url
    def get(path, **kwargs):
        return anon.s.get(anon.base + path, **kwargs)
    anon.get = get

    # anonymous GET /rooms should include is_member explicitly as False
    catalog = anon.get('/rooms')
    assert catalog.status_code == 200
    rooms = catalog.json().get('rooms')
    assert isinstance(rooms, list)
    # find the created room
    found = [r for r in rooms if r.get('name') == rn]
    assert found
    room = found[0]
    assert 'is_member' in room
    assert room['is_member'] is False
