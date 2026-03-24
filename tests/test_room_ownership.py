import uuid


def _reg_and_token(client, prefix='user'):
    suffix = str(uuid.uuid4())[:8]
    email = f'{prefix}_{suffix}@example.com'
    username = f'{prefix}_{suffix}'
    r = client.post('/register', json={'email': email, 'username': username, 'password': 'pass'})
    assert r.status_code == 200
    return r.json()['user'], r.json()['token']


def test_owner_cannot_leave_but_can_delete(client):
    owner, owner_token = _reg_and_token(client, 'owner')
    client.s.headers.update({'Authorization': f'Bearer {owner_token}'})
    rn = f"owneroom_{str(uuid.uuid4())[:8]}"
    r = client.post('/rooms', json={'name': rn})
    assert r.status_code == 200
    rid = r.json()['room']['id']

    # owner attempts to leave -> forbidden
    client.s.headers.update({'Authorization': f'Bearer {owner_token}'})
    lv = client.post(f'/rooms/{rid}/leave')
    assert lv.status_code == 403

    # another user cannot delete the room
    u, t = _reg_and_token(client, 'u')
    client.s.headers.update({'Authorization': f'Bearer {t}'})
    delr = client.s.delete(client.s.base_url + f'/rooms/{rid}')
    assert delr.status_code == 403

    # owner deletes
    client.s.headers.update({'Authorization': f'Bearer {owner_token}'})
    dr = client.s.delete(client.s.base_url + f'/rooms/{rid}')
    assert dr.status_code == 200

    # deleted room is gone
    client.s.headers.update({'Authorization': f'Bearer {owner_token}'})
    gr = client.get(f'/rooms/{rid}')
    assert gr.status_code == 404
