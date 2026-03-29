"""
Tests for the "remove = ban" UI behavior implemented in static/app/lib/rooms.js.

The JS changes rely on three server-side contracts which these tests verify:

1. GET /rooms/{id}  →  room.bans contains the banned user's ID
   (used by the JS to detect whether the current user is banned and show
   the "🚫 You have been banned" notice while hiding Join/Leave/Chat buttons)

2. POST /rooms/{id}/members/remove  →  victim appears in room.bans immediately
   (the "Remove (ban)" button calls this endpoint; the test confirms that the
   server actually records it as a ban, which is the behaviour the button label
   and confirmation dialog communicate to the admin)

3. GET /rooms/{id}/bans  →  each entry has banner_id set to the acting admin
   (used by the Manage panel "Banned users" list to show "banned by <user>")

4. After unban, the victim is no longer in room.bans and can rejoin
   (tests the reverse path that the "Unban" button in the Manage panel triggers)
"""

import uuid


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _register(client, prefix='u'):
    """Register a new unique user and return (user_dict, token)."""
    suffix = uuid.uuid4().hex[:8]
    r = client.post('/register', json={
        'email': f'{prefix}_{suffix}@example.com',
        'username': f'{prefix}_{suffix}',
        'password': 'pw',
    })
    assert r.status_code == 200, r.text
    return r.json()['user'], r.json()['token']


def _auth(client, token):
    client.s.headers.update({'Authorization': f'Bearer {token}'})


def _create_room(client, token, name=None):
    _auth(client, token)
    rn = name or f'room_{uuid.uuid4().hex[:8]}'
    rc = client.post('/rooms', json={'name': rn, 'description': '', 'visibility': 'public'})
    assert rc.status_code == 200, rc.text
    return rc.json()['room']['id']


# ---------------------------------------------------------------------------
# 1. room.bans contains victim id after removal (the "ban notice" contract)
# ---------------------------------------------------------------------------

def test_room_bans_field_contains_removed_user(client):
    """
    GET /rooms/{id} must include the removed user's ID in room.bans so that
    the JS can detect banned status and show the ban notice.
    """
    owner, owner_tok = _register(client, 'bnown')
    victim, victim_tok = _register(client, 'bnvic')

    rid = _create_room(client, owner_tok)

    _auth(client, owner_tok)
    assert client.post(f'/rooms/{rid}/members/add', json={'user_id': victim['id']}).status_code == 200

    # owner removes victim
    assert client.post(f'/rooms/{rid}/members/remove', json={'user_id': victim['id']}).status_code == 200

    # room detail must have victim in bans list
    room_data = client.get(f'/rooms/{rid}').json()['room']
    assert victim['id'] in room_data['bans'], (
        "room.bans must contain the removed user's id so the JS can show the ban notice"
    )


def test_room_bans_info_contains_removed_user(client):
    """
    GET /rooms/{id} must also populate room.bans_info with an entry for the
    removed user (used by the Manage panel "Banned users" list).
    """
    owner, owner_tok = _register(client, 'biown')
    victim, victim_tok = _register(client, 'bivic')

    rid = _create_room(client, owner_tok)

    _auth(client, owner_tok)
    assert client.post(f'/rooms/{rid}/members/add', json={'user_id': victim['id']}).status_code == 200
    assert client.post(f'/rooms/{rid}/members/remove', json={'user_id': victim['id']}).status_code == 200

    room_data = client.get(f'/rooms/{rid}').json()['room']
    bans_info = room_data.get('bans_info', [])
    ban_ids = [b.get('id') for b in bans_info]
    assert victim['id'] in ban_ids, (
        "room.bans_info must include an entry for the removed user"
    )


# ---------------------------------------------------------------------------
# 2. remove = ban: victim cannot rejoin and loses message/room access
# ---------------------------------------------------------------------------

def test_removed_user_cannot_rejoin(client):
    """
    After /members/remove the victim must get 403 on POST /rooms/{id}/join.
    This is the enforcement side of the "Remove (ban)" button.
    """
    owner, owner_tok = _register(client, 'rjown')
    victim, victim_tok = _register(client, 'rjvic')

    rid = _create_room(client, owner_tok)

    _auth(client, owner_tok)
    assert client.post(f'/rooms/{rid}/members/add', json={'user_id': victim['id']}).status_code == 200
    assert client.post(f'/rooms/{rid}/members/remove', json={'user_id': victim['id']}).status_code == 200

    _auth(client, victim_tok)
    jr = client.post(f'/rooms/{rid}/join')
    assert jr.status_code == 403, "Removed (banned) user must not be able to rejoin"


def test_removed_user_cannot_read_messages(client):
    """
    After removal, victim must get 403 on GET /rooms/{id}/messages.
    The JS ban notice hides the "Go to Chat" button; this confirms the API
    enforces the same rule.
    """
    owner, owner_tok = _register(client, 'rmown')
    victim, victim_tok = _register(client, 'rmvic')

    rid = _create_room(client, owner_tok)

    _auth(client, owner_tok)
    assert client.post(f'/rooms/{rid}/members/add', json={'user_id': victim['id']}).status_code == 200

    # victim posts a message while still a member
    _auth(client, victim_tok)
    pm = client.post(f'/rooms/{rid}/messages', json={'text': 'before ban'})
    assert pm.status_code == 200

    # owner removes victim
    _auth(client, owner_tok)
    assert client.post(f'/rooms/{rid}/members/remove', json={'user_id': victim['id']}).status_code == 200

    # victim can no longer read messages
    _auth(client, victim_tok)
    gm = client.get(f'/rooms/{rid}/messages')
    assert gm.status_code == 403, "Banned user must not be able to read room messages"


def test_removed_user_not_in_members_list(client):
    """
    After removal, victim must not appear in room.members.
    The Manage panel "Members" list is built from this; confirming the user
    is gone from that list (and now in bans) validates the Remove (ban) flow.
    """
    owner, owner_tok = _register(client, 'mlown')
    victim, victim_tok = _register(client, 'mlvic')

    rid = _create_room(client, owner_tok)

    _auth(client, owner_tok)
    assert client.post(f'/rooms/{rid}/members/add', json={'user_id': victim['id']}).status_code == 200
    assert client.post(f'/rooms/{rid}/members/remove', json={'user_id': victim['id']}).status_code == 200

    room_data = client.get(f'/rooms/{rid}').json()['room']
    assert victim['id'] not in room_data.get('members', []), (
        "Removed user must not appear in room.members"
    )
    assert victim['id'] in room_data.get('bans', []), (
        "Removed user must appear in room.bans"
    )


# ---------------------------------------------------------------------------
# 3. GET /rooms/{id}/bans returns banner_id (the "banned by X" display contract)
# ---------------------------------------------------------------------------

def test_bans_endpoint_records_banner_id_for_removal(client):
    """
    GET /rooms/{id}/bans must return an entry where banner_id equals the admin
    who performed the removal. The Manage panel "Banned users" list uses this
    to display "banned by <user>".
    """
    owner, owner_tok = _register(client, 'brid_own')
    admin, admin_tok = _register(client, 'brid_adm')
    victim, victim_tok = _register(client, 'brid_vic')

    rid = _create_room(client, owner_tok)

    _auth(client, owner_tok)
    assert client.post(f'/rooms/{rid}/admins/add', json={'user_id': admin['id']}).status_code == 200
    assert client.post(f'/rooms/{rid}/members/add', json={'user_id': victim['id']}).status_code == 200

    # admin performs the Remove (ban)
    _auth(client, admin_tok)
    assert client.post(f'/rooms/{rid}/members/remove', json={'user_id': victim['id']}).status_code == 200

    # check bans endpoint (requires admin/owner auth)
    bres = client.get(f'/rooms/{rid}/bans')
    assert bres.status_code == 200
    bans = bres.json().get('bans', [])
    matching = [b for b in bans if b['banned_id'] == victim['id']]
    assert matching, "Removed user must appear in /bans endpoint"
    assert matching[0]['banner_id'] == admin['id'], (
        "banner_id must be the admin who performed the removal, "
        "so the Manage panel can show 'banned by <admin>'"
    )


def test_bans_endpoint_records_banner_id_for_explicit_ban(client):
    """
    The separate explicit Ban button (not Remove) also calls /ban; confirm
    that banner_id is recorded correctly for that path too.
    """
    owner, owner_tok = _register(client, 'xbown')
    admin, admin_tok = _register(client, 'xbadm')
    victim, victim_tok = _register(client, 'xbvic')

    rid = _create_room(client, owner_tok)

    _auth(client, owner_tok)
    assert client.post(f'/rooms/{rid}/admins/add', json={'user_id': admin['id']}).status_code == 200
    assert client.post(f'/rooms/{rid}/members/add', json={'user_id': victim['id']}).status_code == 200

    _auth(client, admin_tok)
    assert client.post(f'/rooms/{rid}/ban', json={'user_id': victim['id']}).status_code == 200

    bres = client.get(f'/rooms/{rid}/bans')
    assert bres.status_code == 200
    bans = bres.json().get('bans', [])
    matching = [b for b in bans if b['banned_id'] == victim['id']]
    assert matching
    assert matching[0]['banner_id'] == admin['id']


def test_non_admin_cannot_see_bans(client):
    """
    GET /rooms/{id}/bans must return 403 for a regular member.
    Ensures the "Banned users" section in the Manage panel is only visible
    to admins (the server must back up what the UI hides).
    """
    owner, owner_tok = _register(client, 'nbown')
    member, member_tok = _register(client, 'nbmem')

    rid = _create_room(client, owner_tok)

    _auth(client, owner_tok)
    assert client.post(f'/rooms/{rid}/members/add', json={'user_id': member['id']}).status_code == 200

    _auth(client, member_tok)
    bres = client.get(f'/rooms/{rid}/bans')
    assert bres.status_code == 403, "Non-admin must not access /bans"


# ---------------------------------------------------------------------------
# 4. Unban restores access (the "Unban" button reverse path)
# ---------------------------------------------------------------------------

def test_unban_restores_join_access(client):
    """
    After POST /rooms/{id}/unban the victim must be able to rejoin.
    This validates the Manage panel "Unban" button end-to-end.
    """
    owner, owner_tok = _register(client, 'ubown')
    victim, victim_tok = _register(client, 'ubvic')

    rid = _create_room(client, owner_tok)

    _auth(client, owner_tok)
    assert client.post(f'/rooms/{rid}/members/add', json={'user_id': victim['id']}).status_code == 200
    assert client.post(f'/rooms/{rid}/members/remove', json={'user_id': victim['id']}).status_code == 200

    # confirm banned
    _auth(client, victim_tok)
    assert client.post(f'/rooms/{rid}/join').status_code == 403

    # owner unbans
    _auth(client, owner_tok)
    assert client.post(f'/rooms/{rid}/unban', json={'user_id': victim['id']}).status_code == 200

    # victim can now rejoin
    _auth(client, victim_tok)
    jr = client.post(f'/rooms/{rid}/join')
    assert jr.status_code == 200, "Unbanned user must be able to rejoin the room"


def test_unban_removes_user_from_bans_field(client):
    """
    After unban, victim must no longer appear in room.bans.
    The JS ban notice is shown only when the user is in room.bans; once
    unbanned the notice must disappear on next page load.
    """
    owner, owner_tok = _register(client, 'ubfown')
    victim, victim_tok = _register(client, 'ubfvic')

    rid = _create_room(client, owner_tok)

    _auth(client, owner_tok)
    assert client.post(f'/rooms/{rid}/members/add', json={'user_id': victim['id']}).status_code == 200
    assert client.post(f'/rooms/{rid}/members/remove', json={'user_id': victim['id']}).status_code == 200
    assert client.post(f'/rooms/{rid}/unban', json={'user_id': victim['id']}).status_code == 200

    room_data = client.get(f'/rooms/{rid}').json()['room']
    assert victim['id'] not in room_data.get('bans', []), (
        "Unbanned user must not appear in room.bans"
    )


# ---------------------------------------------------------------------------
# 5. GET /users/search — the "Ban a user" form's autocomplete endpoint
# ---------------------------------------------------------------------------

def test_user_search_returns_prefix_matches(client):
    """
    GET /users/search?q=<prefix> must return users whose username starts with
    the query (case-insensitive). This is the endpoint the 'Ban a user'
    search input uses to find users by username.
    """
    # create two users with a distinctive prefix
    unique = uuid.uuid4().hex[:6]
    user_a, tok_a = _register(client, f'srch{unique}a')
    user_b, tok_b = _register(client, f'srch{unique}b')
    # a third user that should NOT match
    _register(client, f'other{uuid.uuid4().hex[:6]}')

    _auth(client, tok_a)
    res = client.get(f'/users/search?q=srch{unique}')
    assert res.status_code == 200
    users = res.json().get('users', [])
    ids = [u['id'] for u in users]
    assert user_a['id'] in ids, "Prefix search must return user_a"
    assert user_b['id'] in ids, "Prefix search must return user_b"


def test_user_search_is_case_insensitive(client):
    """
    The search must be case-insensitive so admins can type in any case.
    """
    unique = uuid.uuid4().hex[:6]
    user, tok = _register(client, f'CaseTst{unique}')

    _auth(client, tok)
    res = client.get(f'/users/search?q=casetst{unique}')
    assert res.status_code == 200
    ids = [u['id'] for u in res.json().get('users', [])]
    assert user['id'] in ids, "Search must be case-insensitive"


def test_user_search_empty_query_returns_empty(client):
    """
    An empty query must return an empty list (not all users).
    """
    _, tok = _register(client, 'srchempty')
    _auth(client, tok)
    res = client.get('/users/search?q=')
    assert res.status_code == 200
    assert res.json().get('users', []) == []


def test_user_search_requires_auth(client):
    """
    GET /users/search must return 401/403 for unauthenticated requests.
    """
    res = client.s.get(client.s.base_url + '/users/search?q=test')
    assert res.status_code in (401, 403), "Unauthenticated search must be rejected"


def test_ban_via_search_and_ban_endpoint(client):
    """
    Full flow simulating the 'Ban a user' form:
    1. Admin searches for a user by username prefix → gets back user id
    2. Admin POSTs /rooms/{id}/ban with that user_id
    3. User appears in /rooms/{id}/bans and cannot rejoin
    """
    owner, owner_tok = _register(client, 'bsown')
    target, target_tok = _register(client, 'bstarget')

    rid = _create_room(client, owner_tok)

    # step 1: search for target
    _auth(client, owner_tok)
    search_res = client.get(f'/users/search?q={target["username"][:5]}')
    assert search_res.status_code == 200
    found = [u for u in search_res.json().get('users', []) if u['id'] == target['id']]
    assert found, "Target user must appear in search results"
    found_id = found[0]['id']

    # step 2: ban using the id from search
    ban_res = client.post(f'/rooms/{rid}/ban', json={'user_id': found_id})
    assert ban_res.status_code == 200

    # step 3: user is banned and cannot join
    _auth(client, target_tok)
    assert client.post(f'/rooms/{rid}/join').status_code == 403

    # also appears in bans list
    _auth(client, owner_tok)
    bans = client.get(f'/rooms/{rid}/bans').json().get('bans', [])
    assert any(b['banned_id'] == target['id'] for b in bans)


# ---------------------------------------------------------------------------
# 6. GET /rooms list — is_banned flag (rooms list badge contract)
# ---------------------------------------------------------------------------

def test_list_rooms_includes_is_banned_true_for_banned_user(client):
    """
    GET /rooms must include is_banned=True for rooms where the requesting
    user has been banned. The JS rooms list uses this to show the 🚫 Banned
    badge and hide the Join button.
    """
    owner, owner_tok = _register(client, 'lbown')
    victim, victim_tok = _register(client, 'lbvic')

    rid = _create_room(client, owner_tok)

    _auth(client, owner_tok)
    assert client.post(f'/rooms/{rid}/members/add', json={'user_id': victim['id']}).status_code == 200
    assert client.post(f'/rooms/{rid}/members/remove', json={'user_id': victim['id']}).status_code == 200

    # request list as victim
    _auth(client, victim_tok)
    res = client.get('/rooms')
    assert res.status_code == 200
    rooms = res.json().get('rooms', [])
    matching = [r for r in rooms if r['id'] == rid]
    assert matching, "Banned room must still appear in the list"
    assert matching[0].get('is_banned') is True, (
        "GET /rooms must set is_banned=True for rooms where the user is banned"
    )


def test_list_rooms_is_banned_false_for_normal_member(client):
    """
    GET /rooms must set is_banned=False (or falsy) for rooms where the user
    is a normal member (not banned). Ensures the badge only appears when appropriate.
    """
    owner, owner_tok = _register(client, 'lbfown')
    member, member_tok = _register(client, 'lbfmem')

    rid = _create_room(client, owner_tok)

    _auth(client, owner_tok)
    assert client.post(f'/rooms/{rid}/members/add', json={'user_id': member['id']}).status_code == 200

    _auth(client, member_tok)
    res = client.get('/rooms')
    assert res.status_code == 200
    rooms = res.json().get('rooms', [])
    matching = [r for r in rooms if r['id'] == rid]
    assert matching
    assert not matching[0].get('is_banned'), (
        "GET /rooms must NOT set is_banned for a room where the user is a normal member"
    )


def test_list_rooms_is_banned_false_after_unban(client):
    """
    After being unbanned, GET /rooms must no longer return is_banned=True for
    that room. Ensures the badge disappears once an admin removes the ban.
    """
    owner, owner_tok = _register(client, 'lbuown')
    victim, victim_tok = _register(client, 'lbuvic')

    rid = _create_room(client, owner_tok)

    _auth(client, owner_tok)
    assert client.post(f'/rooms/{rid}/members/add', json={'user_id': victim['id']}).status_code == 200
    assert client.post(f'/rooms/{rid}/members/remove', json={'user_id': victim['id']}).status_code == 200
    assert client.post(f'/rooms/{rid}/unban', json={'user_id': victim['id']}).status_code == 200

    _auth(client, victim_tok)
    res = client.get('/rooms')
    assert res.status_code == 200
    rooms = res.json().get('rooms', [])
    matching = [r for r in rooms if r['id'] == rid]
    assert matching
    assert not matching[0].get('is_banned'), (
        "After unban, GET /rooms must return is_banned=False for that room"
    )


# ---------------------------------------------------------------------------
# 7. GET /rooms/{id} — graceful banned response (replaces old 403 behavior)
# ---------------------------------------------------------------------------

def test_get_room_returns_200_with_is_banned_for_banned_user(client):
    """
    GET /rooms/{id} must return HTTP 200 (not 403) for a banned user, with
    room.is_banned=True. The JS uses this to render the ban notice instead
    of receiving an opaque error.
    """
    owner, owner_tok = _register(client, 'grbown')
    victim, victim_tok = _register(client, 'grbvic')

    rid = _create_room(client, owner_tok)

    _auth(client, owner_tok)
    assert client.post(f'/rooms/{rid}/members/add', json={'user_id': victim['id']}).status_code == 200
    assert client.post(f'/rooms/{rid}/members/remove', json={'user_id': victim['id']}).status_code == 200

    _auth(client, victim_tok)
    res = client.get(f'/rooms/{rid}')
    assert res.status_code == 200, (
        "GET /rooms/{id} must return 200 for a banned user (graceful response)"
    )
    room = res.json().get('room', {})
    assert room.get('is_banned') is True, (
        "room.is_banned must be True in the response for a banned user"
    )


def test_get_room_banned_response_includes_basic_room_info(client):
    """
    The graceful banned response must still include the room name/description
    so the UI can display context inside the ban notice.
    """
    owner, owner_tok = _register(client, 'grbinfown')
    victim, victim_tok = _register(client, 'grbinfvic')

    rid = _create_room(client, owner_tok)

    _auth(client, owner_tok)
    assert client.post(f'/rooms/{rid}/members/add', json={'user_id': victim['id']}).status_code == 200
    assert client.post(f'/rooms/{rid}/members/remove', json={'user_id': victim['id']}).status_code == 200

    _auth(client, victim_tok)
    room = client.get(f'/rooms/{rid}').json().get('room', {})
    assert room.get('id') == rid
    assert room.get('name')  # name must be present


def test_get_room_banned_response_includes_banned_by(client):
    """
    The graceful banned response must include banned_by with the banning
    admin's username so the UI can show "Banned by: <username>".
    """
    owner, owner_tok = _register(client, 'grbbyown')
    victim, victim_tok = _register(client, 'grbbyvic')

    rid = _create_room(client, owner_tok)

    _auth(client, owner_tok)
    assert client.post(f'/rooms/{rid}/members/add', json={'user_id': victim['id']}).status_code == 200
    assert client.post(f'/rooms/{rid}/members/remove', json={'user_id': victim['id']}).status_code == 200

    _auth(client, victim_tok)
    room = client.get(f'/rooms/{rid}').json().get('room', {})
    banned_by = room.get('banned_by')
    assert banned_by is not None, "room.banned_by must be present in the graceful banned response"
    assert banned_by.get('id') == owner['id'], (
        "banned_by.id must be the user who performed the ban"
    )
    assert banned_by.get('username'), "banned_by must include the banning user's username"


def test_get_room_banned_hides_members_list(client):
    """
    The graceful banned response must NOT expose the full members/admins lists.
    Banned users should not be able to enumerate who is in the room.
    """
    owner, owner_tok = _register(client, 'grbhideown')
    victim, victim_tok = _register(client, 'grbhidevic')
    other, other_tok = _register(client, 'grbhideoth')

    rid = _create_room(client, owner_tok)

    _auth(client, owner_tok)
    assert client.post(f'/rooms/{rid}/members/add', json={'user_id': victim['id']}).status_code == 200
    assert client.post(f'/rooms/{rid}/members/add', json={'user_id': other['id']}).status_code == 200
    assert client.post(f'/rooms/{rid}/members/remove', json={'user_id': victim['id']}).status_code == 200

    _auth(client, victim_tok)
    room = client.get(f'/rooms/{rid}').json().get('room', {})
    assert room.get('is_banned') is True
    members = room.get('members', [])
    assert other['id'] not in members, (
        "Banned user must not see the members list of the room they are banned from"
    )


def test_get_room_is_banned_false_for_normal_member(client):
    """
    GET /rooms/{id} must include is_banned=False for a normal member.
    """
    owner, owner_tok = _register(client, 'grbnotown')
    member, member_tok = _register(client, 'grbnotmem')

    rid = _create_room(client, owner_tok)

    _auth(client, owner_tok)
    assert client.post(f'/rooms/{rid}/members/add', json={'user_id': member['id']}).status_code == 200

    _auth(client, member_tok)
    room = client.get(f'/rooms/{rid}').json().get('room', {})
    assert room.get('is_banned') is False, (
        "GET /rooms/{id} must return is_banned=False for a normal member"
    )
