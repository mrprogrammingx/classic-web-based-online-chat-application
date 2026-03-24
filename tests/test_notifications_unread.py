import time
import base64


def _reg_and_token(client, prefix):
    import uuid
    s = client
    suffix = str(uuid.uuid4())[:8]
    email = f'{prefix}_{suffix}@example.com'
    r = s.post('/register', json={'email': email, 'username': f'{prefix}_{suffix}', 'password': 'pass'})
    assert r.status_code == 200
    return r.json()['user'], r.json()['token']


def test_unread_room_indicator(client):
    s = client
    owner, owner_token = _reg_and_token(s, 'owner_room')
    member, member_token = _reg_and_token(s, 'member_room')

    # owner creates private room and invites member
    s.s.headers.update({'Authorization': f'Bearer {owner_token}'})
    rn = f"notifroom_{int(time.time())}"
    rc = s.post('/rooms', json={'name': rn, 'visibility': 'private'})
    assert rc.status_code == 200
    rid = rc.json()['room']['id']
    assert s.post(f'/rooms/{rid}/invite', json={'invitee_id': member['id']}).status_code == 200

    # member accepts invite
    s.s.headers.update({'Authorization': f'Bearer {member_token}'})
    invs = s.get(f'/rooms/{rid}/invites').json().get('invites', [])
    invite_id = None
    for inv in invs:
        if inv.get('room_id') == rid:
            invite_id = inv['id']
            break
    assert invite_id is not None
    assert s.post(f'/rooms/{rid}/invites/{invite_id}/accept').status_code == 200

    # owner posts a message
    s.s.headers.update({'Authorization': f'Bearer {owner_token}'})
    assert s.post(f'/rooms/{rid}/messages', json={'text': 'hello members'}) .status_code == 200

    # member should see unread in notifications
    s.s.headers.update({'Authorization': f'Bearer {member_token}'})
    summary = s.get('/notifications/unread-summary').json()
    rooms = {r['room_id']: r['unread_count'] for r in summary.get('rooms', [])}
    assert rooms.get(rid, 0) >= 1

    # when member opens the room, unread clears
    msgs = s.get(f'/rooms/{rid}/messages')
    assert msgs.status_code == 200
    summary2 = s.get('/notifications/unread-summary').json()
    rooms2 = {r['room_id']: r['unread_count'] for r in summary2.get('rooms', [])}
    assert rooms2.get(rid, 0) == 0 or rid not in rooms2


def test_unread_dialog_indicator(client):
    s = client
    a, a_tok = _reg_and_token(s, 'a_dialog')
    b, b_tok = _reg_and_token(s, 'b_dialog')

    # establish friendship
    s.s.headers.update({'Authorization': f'Bearer {a_tok}'})
    assert s.post('/friends/request', json={'friend_id': b['id']}).status_code == 200
    s.s.headers.update({'Authorization': f'Bearer {b_tok}'})
    reqs = s.get('/friends/requests').json().get('requests', [])
    req_id = None
    for rq in reqs:
        if rq.get('from_id') == a['id']:
            req_id = rq['id']
            break
    assert req_id is not None
    assert s.post('/friends/requests/respond', json={'request_id': req_id, 'action': 'accept'}).status_code == 200

    # a sends dialog message to b
    s.s.headers.update({'Authorization': f'Bearer {a_tok}'})
    assert s.post(f"/dialogs/{b['id']}/messages", json={'text': 'hi b'}) .status_code == 200

    # b should see unread dialog
    s.s.headers.update({'Authorization': f'Bearer {b_tok}'})
    summary = s.get('/notifications/unread-summary').json()
    dialogs = {d['other_id']: d['unread_count'] for d in summary.get('dialogs', [])}
    assert dialogs.get(a['id'], 0) >= 1

    # when b opens dialog, unread clears
    msgs = s.get(f"/dialogs/{a['id']}/messages")
    assert msgs.status_code == 200
    summary2 = s.get('/notifications/unread-summary').json()
    dialogs2 = {d['other_id']: d['unread_count'] for d in summary2.get('dialogs', [])}
    assert dialogs2.get(a['id'], 0) == 0 or a['id'] not in dialogs2
