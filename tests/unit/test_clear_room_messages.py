import time


def test_clear_room_messages_as_owner(client):
    # register user and set auth header
    import uuid
    suffix = str(uuid.uuid4())[:8]
    email = f'clr_{suffix}@example.com'
    username = f'clr_{suffix}'
    reg = client.post('/register', json={'email': email, 'username': username, 'password': 'pass'})
    assert reg.status_code == 200
    token = reg.json().get('token')
    assert token
    client.s.headers.update({'Authorization': f'Bearer {token}'})
    # create a room with unique name
    import uuid as _uuid
    rn = f"clear-room-test-{str(_uuid.uuid4())[:8]}"
    r = client.post('/rooms', json={'name': rn}).json()
    assert r and 'room' in r
    room_id = r['room']['id']
    # post a couple of messages
    for i in range(3):
        p = client.post(f'/rooms/{room_id}/messages', json={'text': f'msg {i}'}).json()
        assert p and 'message' in p
    # ensure messages exist
    lm = client.get(f'/rooms/{room_id}/messages').json()
    assert lm and 'messages' in lm and len(lm['messages']) >= 3
    # clear messages as owner
    clr = client.post(f'/rooms/{room_id}/messages/clear')
    assert clr.status_code == 200
    # ensure messages are gone
    lm2 = client.get(f'/rooms/{room_id}/messages').json()
    assert lm2 and 'messages' in lm2 and len(lm2['messages']) == 0
