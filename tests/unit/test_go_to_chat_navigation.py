"""
Tests for the "Go to Chat" navigation contract.

When a user clicks "Go to Chat" on a room, the browser navigates to
/static/chat/index.html?room=<id>. On that page, bootstrap.js reads the ?room=
query parameter and stores it in window.__REQUESTED_ROOM, then calls loadRooms().
loadRooms() must select the correct room — including rooms that are NOT in the
default /rooms list (e.g. private rooms, or rooms beyond the pagination limit).

These tests verify the server-side contract that makes this work:
  - GET /rooms?q=<name> finds the room by name (search)
  - GET /rooms/{id}     always returns the room for an authenticated member,
                        even if it would not appear in the default /rooms listing
                        (e.g. private rooms)
"""

import uuid


def _reg(client, prefix='gtc'):
    suffix = uuid.uuid4().hex[:8]
    r = client.post('/register', json={
        'email': f'{prefix}_{suffix}@example.com',
        'username': f'{prefix}_{suffix}',
        'password': 'pw',
    })
    assert r.status_code == 200
    return r.json()['user'], r.json()['token']


def _auth(client, token):
    client.s.headers.update({'Authorization': f'Bearer {token}'})


def _make_room(client, token, name=None, visibility='public'):
    _auth(client, token)
    name = name or f'room_{uuid.uuid4().hex[:8]}'
    rc = client.post('/rooms', json={'name': name, 'description': '', 'visibility': visibility})
    assert rc.status_code == 200, rc.text
    return rc.json()['room']['id'], name


# ---------------------------------------------------------------------------
# 1. GET /rooms/{id} works for a public room member
# ---------------------------------------------------------------------------

def test_get_room_by_id_works_for_member(client):
    """
    GET /rooms/{id} must return the room for an authenticated member.
    This is the direct-fetch fallback used when the room is not in the
    default /rooms list that was loaded by loadRooms().
    """
    owner, owner_tok = _reg(client, 'gtcown')
    member, member_tok = _reg(client, 'gtcmem')

    rid, _ = _make_room(client, owner_tok)

    _auth(client, owner_tok)
    assert client.post(f'/rooms/{rid}/members/add', json={'user_id': member['id']}).status_code == 200

    _auth(client, member_tok)
    res = client.get(f'/rooms/{rid}')
    assert res.status_code == 200
    room = res.json()['room']
    assert room['id'] == rid
    assert room.get('is_banned') is False


# ---------------------------------------------------------------------------
# 2. GET /rooms/{id} works for a private room that the user is a member of
# ---------------------------------------------------------------------------

def test_get_room_by_id_works_for_private_room_member(client):
    """
    Private rooms do NOT appear in the default GET /rooms list (visibility=public).
    The Go to Chat fallback fetches GET /rooms/{id} directly — this must succeed
    for a member of the private room.
    """
    owner, owner_tok = _reg(client, 'gtcpriv')
    member, member_tok = _reg(client, 'gtcprmem')

    rid, _ = _make_room(client, owner_tok, visibility='private')

    _auth(client, owner_tok)
    assert client.post(f'/rooms/{rid}/members/add', json={'user_id': member['id']}).status_code == 200

    # confirm the room does NOT appear in the default public list
    _auth(client, member_tok)
    pub_list = client.get('/rooms').json().get('rooms', [])
    assert not any(r['id'] == rid for r in pub_list), (
        "Private room must not appear in the default public /rooms list"
    )

    # but GET /rooms/{id} must work directly
    res = client.get(f'/rooms/{rid}')
    assert res.status_code == 200, (
        "GET /rooms/{id} must return 200 for a member of a private room — "
        "this is what the Go to Chat fallback fetch relies on"
    )
    assert res.json()['room']['id'] == rid


# ---------------------------------------------------------------------------
# 3. GET /rooms/{id} returns all fields needed by selectRoom()
# ---------------------------------------------------------------------------

def test_get_room_by_id_returns_fields_needed_by_select_room(client):
    """
    The direct-fetch fallback passes the room object straight to selectRoom().
    That function uses: id, name, members (for member panel), admins, owner_id.
    All must be present.
    """
    owner, owner_tok = _reg(client, 'gtcfields')
    rid, rname = _make_room(client, owner_tok)

    _auth(client, owner_tok)
    room = client.get(f'/rooms/{rid}').json()['room']

    assert room.get('id') == rid
    assert room.get('name') == rname
    assert 'members' in room or 'members_info' in room
    assert 'admins' in room or 'admins_info' in room
    assert 'owner_id' in room or 'owner' in room


# ---------------------------------------------------------------------------
# 4. GET /rooms/{id} returns 403/404 for a non-member of a private room
# ---------------------------------------------------------------------------

def test_get_private_room_by_id_denied_for_non_member(client):
    """
    A non-member must NOT be able to access a private room directly.
    The Go to Chat button must not expose private rooms to outsiders.
    """
    owner, owner_tok = _reg(client, 'gtcprivdeny')
    outsider, outsider_tok = _reg(client, 'gtcout')

    rid, _ = _make_room(client, owner_tok, visibility='private')

    _auth(client, outsider_tok)
    res = client.get(f'/rooms/{rid}')
    assert res.status_code in (403, 404), (
        "Non-member must not be able to fetch a private room by id"
    )


# ---------------------------------------------------------------------------
# 5. GET /rooms?q=<name> can locate a room by exact name (search path)
# ---------------------------------------------------------------------------

def test_search_finds_public_room_by_exact_name(client):
    """
    GET /rooms?q=<name> must return the room when the query matches the room name.
    This is the primary path used before the direct-fetch fallback.
    """
    owner, owner_tok = _reg(client, 'gtcsearch')
    unique = uuid.uuid4().hex[:8]
    rname = f'gtcroom_{unique}'
    rid, _ = _make_room(client, owner_tok, name=rname)

    _auth(client, owner_tok)
    res = client.get(f'/rooms?q={unique}')
    assert res.status_code == 200
    rooms = res.json().get('rooms', [])
    assert any(r['id'] == rid for r in rooms), (
        f"GET /rooms?q={unique} must return the room named {rname!r}"
    )


# ---------------------------------------------------------------------------
# 6. GET /rooms?q= with visibility=all finds private rooms for their members
# ---------------------------------------------------------------------------

def test_search_with_visibility_all_finds_private_room(client):
    """
    GET /rooms?q=<name>&visibility=all must include private rooms where the
    authenticated user is a member. This is another path for resolving private
    rooms when navigating via Go to Chat.
    """
    owner, owner_tok = _reg(client, 'gtcallsrch')
    unique = uuid.uuid4().hex[:8]
    rname = f'privroom_{unique}'
    rid, _ = _make_room(client, owner_tok, name=rname, visibility='private')

    _auth(client, owner_tok)
    res = client.get(f'/rooms?q={unique}&visibility=all')
    assert res.status_code == 200
    rooms = res.json().get('rooms', [])
    assert any(r['id'] == rid for r in rooms), (
        "GET /rooms?q=<name>&visibility=all must include private rooms the user is a member of"
    )


# ---------------------------------------------------------------------------
# 7. Non-member outsider cannot use GET /rooms?q= to discover private rooms
# ---------------------------------------------------------------------------

def test_search_visibility_all_does_not_expose_private_rooms_to_outsiders(client):
    """
    GET /rooms?visibility=all must not include private rooms for non-members.
    """
    owner, owner_tok = _reg(client, 'gtcprvsec')
    outsider, outsider_tok = _reg(client, 'gtcprvout')
    unique = uuid.uuid4().hex[:8]
    rid, _ = _make_room(client, owner_tok, name=f'secret_{unique}', visibility='private')

    _auth(client, outsider_tok)
    res = client.get(f'/rooms?q={unique}&visibility=all')
    assert res.status_code == 200
    rooms = res.json().get('rooms', [])
    assert not any(r['id'] == rid for r in rooms), (
        "Private rooms must not be visible to non-members via search"
    )
