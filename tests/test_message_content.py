import uuid
import os


def _reg_and_token(client, prefix='u'):
    suffix = str(uuid.uuid4())[:8]
    email = f'{prefix}_{suffix}@example.com'
    username = f'{prefix}_{suffix}'
    r = client.post('/register', json={'email': email, 'username': username, 'password': 'pw'})
    assert r.status_code == 200
    return r.json()['user'], r.json()['token']


def test_room_message_content_and_reply_and_size(client):
    owner, ot = _reg_and_token(client, 'owner')
    member, mt = _reg_and_token(client, 'mem')

    # create room and add member
    client.s.headers.update({'Authorization': f'Bearer {ot}'})
    rn = f"msgc_{uuid.uuid4().hex[:8]}"
    rc = client.post('/rooms', json={'name': rn, 'visibility': 'public'})
    assert rc.status_code == 200
    rid = rc.json()['room']['id']
    assert client.post(f'/rooms/{rid}/members/add', json={'user_id': member['id']}).status_code == 200

    # member posts plain text
    client.s.headers.update({'Authorization': f'Bearer {mt}'})
    r1 = client.post(f'/rooms/{rid}/messages', json={'text': 'hello'})
    assert r1.status_code == 200

    # post multiline
    r2 = client.post(f'/rooms/{rid}/messages', json={'text': 'line1\nline2\nline3'})
    assert r2.status_code == 200

    # emoji
    r3 = client.post(f'/rooms/{rid}/messages', json={'text': 'smile 😊'})
    assert r3.status_code == 200

    # reply to previous message
    mid = r1.json()['message']['id']
    rr = client.post(f'/rooms/{rid}/messages', json={'text': 'reply here', 'reply_to': mid})
    assert rr.status_code == 200
    assert rr.json()['message'].get('reply_to') == mid

    # too long message ( >3KB )
    long_text = 'x' * (3 * 1024 + 10)
    bad = client.post(f'/rooms/{rid}/messages', json={'text': long_text})
    assert bad.status_code == 400


def test_dialog_message_content_and_reply_and_size(client):
    a, ta = _reg_and_token(client, 'a')
    b, tb = _reg_and_token(client, 'b')

    # make them friends
    client.s.headers.update({'Authorization': f'Bearer {ta}'})
    assert client.post('/friends/request', json={'username': b['username']}).status_code == 200
    client.s.headers.update({'Authorization': f'Bearer {tb}'})
    reqs = client.get('/friends/requests')
    reqs_json = reqs.json().get('requests', [])
    rid = [r['id'] for r in reqs_json if r['username'] == a['username']][-1]
    assert client.post('/friends/requests/respond', json={'request_id': rid, 'action': 'accept'}).status_code == 200

    # send plain, multiline, emoji
    client.s.headers.update({'Authorization': f'Bearer {ta}'})
    s1 = client.post(f'/dialogs/{b["id"]}/messages', json={'text': 'hello dialog'})
    assert s1.status_code == 200
    s2 = client.post(f'/dialogs/{b["id"]}/messages', json={'text': 'a\nb\nc'})
    assert s2.status_code == 200
    s3 = client.post(f'/dialogs/{b["id"]}/messages', json={'text': 'emoji 👍'})
    assert s3.status_code == 200

    # reply
    mid = s1.json()['message']['id']
    sr = client.post(f'/dialogs/{b["id"]}/messages', json={'text': 'dialog reply', 'reply_to': mid})
    assert sr.status_code == 200
    assert sr.json()['message'].get('reply_to') == mid

    # too long
    long_text = 'x' * (3 * 1024 + 5)
    bad = client.post(f'/dialogs/{b["id"]}/messages', json={'text': long_text})
    assert bad.status_code == 400
