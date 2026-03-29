"""Tests for Phase 5 chat features:
- Room members online endpoint
- Dialog read_only flag on ban
- Room access denial after ban
- Classic web chat CSS overrides
"""
import uuid
import time


def _reg(client, prefix='u'):
    suffix = str(uuid.uuid4())[:8]
    email = f'{prefix}_{suffix}@example.com'
    username = f'{prefix}_{suffix}'
    r = client.post('/register', json={'email': email, 'username': username, 'password': 'pw'})
    assert r.status_code == 200
    return r.json()['user'], r.json()['token']


def _make_friends(client, user_a, token_a, user_b, token_b):
    """Helper to make two users friends via the friend request flow."""
    # A sends friend request to B
    client.s.headers.update({'Authorization': f'Bearer {token_a}'})
    client.post('/friends/request', json={'username': user_b['username'], 'message': 'hi'})
    # B lists incoming requests and accepts A's request
    client.s.headers.update({'Authorization': f'Bearer {token_b}'})
    res = client.get('/friends/requests')
    reqs = res.json().get('requests', [])
    for req in reqs:
        if req.get('from_id') == user_a['id'] or req.get('from_username') == user_a.get('username'):
            client.post('/friends/requests/respond', json={'request_id': req['id'], 'action': 'accept'})
            return
    # fallback: mutual add
    client.post('/friends/add', json={'friend_id': user_a['id']})


# ── Room members online ─────────────────────────────────────────────────

def test_rooms_members_online_empty_when_no_rooms(client):
    """GET /rooms/members-online returns empty list when user has no rooms."""
    user, token = _reg(client, 'rmemb')
    client.s.headers.update({'Authorization': f'Bearer {token}'})
    res = client.get('/rooms/members-online')
    assert res.status_code == 200
    data = res.json()
    assert data['rooms'] == []


def test_rooms_members_online_returns_members(client):
    """GET /rooms/members-online returns rooms with member names and online flags."""
    owner, owner_token = _reg(client, 'rmo_owner')
    member, member_token = _reg(client, 'rmo_member')

    # owner creates room
    client.s.headers.update({'Authorization': f'Bearer {owner_token}'})
    rn = f'rmo_room_{uuid.uuid4().hex[:8]}'
    r = client.post('/rooms', json={'name': rn, 'visibility': 'public'})
    assert r.status_code == 200
    room_id = r.json()['room']['id']

    # member joins
    client.s.headers.update({'Authorization': f'Bearer {member_token}'})
    r = client.post(f'/rooms/{room_id}/join')
    assert r.status_code == 200

    # member fetches members-online
    res = client.get('/rooms/members-online')
    assert res.status_code == 200
    data = res.json()
    room_ids = [rm['id'] for rm in data['rooms']]
    assert room_id in room_ids

    target_room = [rm for rm in data['rooms'] if rm['id'] == room_id][0]
    member_ids = [m['id'] for m in target_room['members']]
    assert owner['id'] in member_ids
    assert member['id'] in member_ids
    # each member has 'name' and 'online' fields
    for m in target_room['members']:
        assert 'name' in m
        assert 'online' in m


# ── Dialog read_only flag on ban ─────────────────────────────────────────

def test_dialog_history_read_only_after_ban(client):
    """GET /dialogs/{id}/messages should return read_only=True when ban exists."""
    user_a, token_a = _reg(client, 'dlg_a')
    user_b, token_b = _reg(client, 'dlg_b')

    # make them friends via the request/accept flow
    _make_friends(client, user_a, token_a, user_b, token_b)

    # send a message from A to B
    client.s.headers.update({'Authorization': f'Bearer {token_a}'})
    r = client.post(f'/dialogs/{user_b["id"]}/messages', json={'text': 'hello before ban'})
    assert r.status_code == 200

    # check read_only is False before ban
    res = client.get(f'/dialogs/{user_b["id"]}/messages')
    assert res.status_code == 200
    assert res.json()['read_only'] is False

    # A bans B
    client.post('/ban', json={'banned_id': user_b['id']})

    # check read_only is True after ban — messages are still returned
    res = client.get(f'/dialogs/{user_b["id"]}/messages')
    assert res.status_code == 200
    data = res.json()
    assert data['read_only'] is True
    assert len(data['messages']) >= 1

    # B also sees read_only
    client.s.headers.update({'Authorization': f'Bearer {token_b}'})
    res = client.get(f'/dialogs/{user_a["id"]}/messages')
    assert res.status_code == 200
    assert res.json()['read_only'] is True


def test_dialog_send_blocked_after_ban(client):
    """POST /dialogs/{id}/messages should return 403 when ban exists."""
    user_a, token_a = _reg(client, 'dlgsend_a')
    user_b, token_b = _reg(client, 'dlgsend_b')

    # make friends
    _make_friends(client, user_a, token_a, user_b, token_b)

    # A bans B
    client.s.headers.update({'Authorization': f'Bearer {token_a}'})
    client.post('/ban', json={'banned_id': user_b['id']})

    # A tries to send — should be 403
    r = client.post(f'/dialogs/{user_b["id"]}/messages', json={'text': 'hi'})
    assert r.status_code == 403

    # B tries to send — should be 403
    client.s.headers.update({'Authorization': f'Bearer {token_b}'})
    r = client.post(f'/dialogs/{user_a["id"]}/messages', json={'text': 'hi'})
    assert r.status_code == 403


# ── Room access denied after ban ─────────────────────────────────────────

def test_room_messages_403_after_ban(client):
    """GET /rooms/{id}/messages should return 403 for a banned user."""
    owner, owner_token = _reg(client, 'rmban_own')
    member, member_token = _reg(client, 'rmban_mem')

    # create room and member joins
    client.s.headers.update({'Authorization': f'Bearer {owner_token}'})
    rn = f'banroom_{uuid.uuid4().hex[:8]}'
    r = client.post('/rooms', json={'name': rn, 'visibility': 'public'})
    assert r.status_code == 200
    room_id = r.json()['room']['id']

    client.s.headers.update({'Authorization': f'Bearer {member_token}'})
    client.post(f'/rooms/{room_id}/join')

    # member can read messages
    res = client.get(f'/rooms/{room_id}/messages')
    assert res.status_code == 200

    # owner bans member
    client.s.headers.update({'Authorization': f'Bearer {owner_token}'})
    r = client.post(f'/rooms/{room_id}/ban', json={'user_id': member['id']})
    assert r.status_code == 200

    # member tries to read messages — 403
    client.s.headers.update({'Authorization': f'Bearer {member_token}'})
    res = client.get(f'/rooms/{room_id}/messages')
    assert res.status_code == 403

    # member tries to list files — 403
    res = client.get(f'/rooms/{room_id}/files')
    assert res.status_code == 403


def test_room_files_403_after_ban(client):
    """Banned user cannot download individual room files."""
    owner, owner_token = _reg(client, 'rfban_own')
    member, member_token = _reg(client, 'rfban_mem')

    # create room
    client.s.headers.update({'Authorization': f'Bearer {owner_token}'})
    rn = f'filebanroom_{uuid.uuid4().hex[:8]}'
    r = client.post('/rooms', json={'name': rn, 'visibility': 'public'})
    assert r.status_code == 200
    room_id = r.json()['room']['id']

    # member joins
    client.s.headers.update({'Authorization': f'Bearer {member_token}'})
    client.post(f'/rooms/{room_id}/join')

    # owner uploads a file
    client.s.headers.update({'Authorization': f'Bearer {owner_token}'})
    import io
    r = client.post(
        f'/rooms/{room_id}/files',
        files={'file': ('test.txt', io.BytesIO(b'hello'), 'text/plain')},
    )
    assert r.status_code == 200
    file_id = r.json()['file']['id']

    # member can access file before ban
    client.s.headers.update({'Authorization': f'Bearer {member_token}'})
    res = client.get(f'/rooms/{room_id}/files/{file_id}')
    assert res.status_code == 200

    # owner bans member
    client.s.headers.update({'Authorization': f'Bearer {owner_token}'})
    client.post(f'/rooms/{room_id}/ban', json={'user_id': member['id']})

    # member tries to download — 403
    client.s.headers.update({'Authorization': f'Bearer {member_token}'})
    res = client.get(f'/rooms/{room_id}/files/{file_id}')
    assert res.status_code == 403


# ── CSS classic web chat ─────────────────────────────────────────────────

def test_css_has_classic_chat_overrides(client):
    """The CSS file should contain classic web chat override rules."""
    res = client.get('/static/styles.css')
    assert res.status_code == 200
    css = res.text
    # flat messages (no gradient)
    assert '.messages{background:#fafafa}' in css
    # flat message bubbles
    assert 'box-shadow:none' in css
    # frozen bar styles
    assert '.frozen-bar{' in css
    # room members section
    assert '.room-members-list' in css
