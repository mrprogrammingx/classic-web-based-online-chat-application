"""Comprehensive tests for the online / AFK / offline presence system.

Covers:
  1. Single-user status via GET /presence/{user_id}
  2. Batch status via GET /presence?ids=...
  3. Room members-online endpoint status field
  4. Edge cases: multiple tabs, mixed freshness, tab close, re-heartbeat
  5. Heartbeat validation & error handling
  6. Status sorting in /rooms/members-online
"""

import base64
import json
import os
import sqlite3
import time
import uuid

import pytest


# ── helpers ──────────────────────────────────────────────────────────────

# The server enforces min AFK_SECONDS of 5 (test mode) or 10 (production).
# Time-based tests that `sleep()` only work when the server was started with
# a small AFK threshold (≤ 10 s).  Detect this by checking the env var set
# by conftest (conftest sets AFK_SECONDS=3 → server computes max(3,5)=5).
_server_afk = max(int(os.getenv('AFK_SECONDS', '60')), 5)
_needs_fast_afk = pytest.mark.skipif(
    _server_afk > 10,
    reason=f'time-based AFK test requires AFK_SECONDS ≤ 10 (got {_server_afk})',
)

def _parse_jwt(token: str) -> dict:
    """Decode JWT payload without signature verification."""
    parts = token.split('.')
    payload = parts[1] + '=' * (-len(parts[1]) % 4)
    return json.loads(base64.urlsafe_b64decode(payload))


def _register(client, prefix='u'):
    suffix = uuid.uuid4().hex[:8]
    email = f'{prefix}_{suffix}@example.com'
    username = f'{prefix}_{suffix}'
    r = client.post('/register', json={'email': email, 'username': username, 'password': 'pw'})
    assert r.status_code == 200
    data = r.json()
    return data['user'], data['token']


def _heartbeat(client, token, tab_id=None, jti=None):
    """Send a heartbeat for a given token. Returns the tab_id used."""
    if jti is None:
        jti = _parse_jwt(token).get('jti')
    if tab_id is None:
        tab_id = 'tab-' + uuid.uuid4().hex[:8]
    r = client.post(
        '/presence/heartbeat',
        headers={'Authorization': f'Bearer {token}'},
        json={'tab_id': tab_id, 'jti': jti},
    )
    assert r.status_code == 200
    return tab_id


def _status(client, user_id):
    """GET /presence/{user_id} and return the status string."""
    r = client.get(f'/presence/{user_id}')
    assert r.status_code == 200
    return r.json()['status']


def _batch_status(client, *user_ids):
    """GET /presence?ids=... and return the statuses dict."""
    ids = ','.join(str(uid) for uid in user_ids)
    r = client.get(f'/presence?ids={ids}')
    assert r.status_code == 200
    return r.json().get('statuses', {})


def _db_path():
    from core.config import DB_PATH
    return os.path.join(os.getcwd(), DB_PATH)


def _insert_stale_tab(user_id, jti, tab_id=None, age_extra=120):
    """Insert a tab_presence row with last_active older than AFK_SECONDS.

    We default to age_extra=120 so the row is well past the AFK threshold
    regardless of server config (min 5 s in test-mode, default 60 s).
    """
    if tab_id is None:
        tab_id = 'tab-stale-' + uuid.uuid4().hex[:8]
    old_ts = int(time.time()) - age_extra
    conn = sqlite3.connect(_db_path())
    try:
        conn.execute(
            'INSERT OR REPLACE INTO tab_presence '
            '(tab_id, jti, user_id, created_at, last_active, user_agent, ip) '
            'VALUES (?, ?, ?, ?, ?, ?, ?)',
            (tab_id, jti, user_id, old_ts, old_ts, 'pytest', '127.0.0.1'),
        )
        conn.commit()
    finally:
        conn.close()
    return tab_id


def _delete_all_tabs(user_id):
    """Remove all tab_presence rows for a user (simulate all tabs closed)."""
    conn = sqlite3.connect(_db_path())
    try:
        conn.execute('DELETE FROM tab_presence WHERE user_id = ?', (user_id,))
        conn.commit()
    finally:
        conn.close()


def _make_friends(client, user_a, token_a, user_b, token_b):
    """Make two users friends via the request/accept flow."""
    client.s.headers.update({'Authorization': f'Bearer {token_a}'})
    client.post('/friends/request', json={'username': user_b['username'], 'message': 'hi'})
    client.s.headers.update({'Authorization': f'Bearer {token_b}'})
    res = client.get('/friends/requests')
    for rq in res.json().get('requests', []):
        if rq.get('from_id') == user_a['id']:
            client.post('/friends/requests/respond', json={'request_id': rq['id'], 'action': 'accept'})
            return
    client.post('/friends/add', json={'friend_id': user_a['id']})


# ═══════════════════════════════════════════════════════════════════════
# 1. Basic single-user presence states
# ═══════════════════════════════════════════════════════════════════════

class TestSingleUserPresence:
    """GET /presence/{user_id} — online / AFK / offline rules."""

    def test_new_user_is_offline(self, client):
        """A freshly registered user with no heartbeat is offline."""
        user, token = _register(client, 'newoff')
        assert _status(client, user['id']) == 'offline'

    def test_heartbeat_makes_user_online(self, client):
        """Sending a heartbeat immediately sets the user to online."""
        user, token = _register(client, 'hbon')
        _heartbeat(client, token)
        assert _status(client, user['id']) == 'online'

    def test_stale_tab_makes_user_afk(self, client):
        """A user with only stale tab_presence rows is AFK."""
        user, token = _register(client, 'stafk')
        jti = _parse_jwt(token)['jti']
        _insert_stale_tab(user['id'], jti)
        assert _status(client, user['id']) == 'AFK'

    def test_closed_tab_makes_user_offline(self, client):
        """After closing the only tab, user becomes offline."""
        user, token = _register(client, 'cloff')
        tab = _heartbeat(client, token)
        assert _status(client, user['id']) == 'online'
        client.s.headers.update({'Authorization': f'Bearer {token}'})
        client.post('/presence/close', json={'tab_id': tab})
        assert _status(client, user['id']) == 'offline'

    @_needs_fast_afk
    def test_afk_after_time_passes(self, client):
        """User transitions from online to AFK after AFK_SECONDS elapse.

        conftest sets AFK_SECONDS=3. We sleep 6 s (well past the cutoff)."""
        user, token = _register(client, 'afktm')
        _heartbeat(client, token)
        assert _status(client, user['id']) == 'online'
        time.sleep(6)
        st = _status(client, user['id'])
        assert st == 'AFK', f'expected AFK, got {st}'

    def test_re_heartbeat_recovers_from_afk(self, client):
        """A user who was AFK becomes online again after a fresh heartbeat."""
        user, token = _register(client, 'reafk')
        jti = _parse_jwt(token)['jti']
        tab = _insert_stale_tab(user['id'], jti)
        assert _status(client, user['id']) == 'AFK'
        # Send a fresh heartbeat on the same tab
        _heartbeat(client, token, tab_id=tab)
        assert _status(client, user['id']) == 'online'

    def test_no_tabs_means_offline_not_afk(self, client):
        """With zero tab_presence rows, status must be offline, never AFK."""
        user, token = _register(client, 'notab')
        _delete_all_tabs(user['id'])
        assert _status(client, user['id']) == 'offline'


# ═══════════════════════════════════════════════════════════════════════
# 2. Multiple tabs
# ═══════════════════════════════════════════════════════════════════════

class TestMultipleTabs:
    """Presence with more than one tab open."""

    def test_two_tabs_both_fresh_is_online(self, client):
        """Two fresh tabs → online."""
        user, token = _register(client, 'mt1')
        _heartbeat(client, token)
        _heartbeat(client, token)
        assert _status(client, user['id']) == 'online'

    def test_one_fresh_one_stale_is_online(self, client):
        """One stale tab + one fresh tab → online (at-least-one rule)."""
        user, token = _register(client, 'mt2')
        jti = _parse_jwt(token)['jti']
        _insert_stale_tab(user['id'], jti)
        _heartbeat(client, token)
        assert _status(client, user['id']) == 'online'

    def test_all_stale_tabs_is_afk(self, client):
        """Multiple stale tabs with no fresh one → AFK."""
        user, token = _register(client, 'mt3')
        jti = _parse_jwt(token)['jti']
        _insert_stale_tab(user['id'], jti, tab_id='stale-a-' + uuid.uuid4().hex[:6])
        _insert_stale_tab(user['id'], jti, tab_id='stale-b-' + uuid.uuid4().hex[:6])
        assert _status(client, user['id']) == 'AFK'

    def test_close_fresh_tab_leaves_stale_is_afk(self, client):
        """Close the only fresh tab while a stale one remains → AFK."""
        user, token = _register(client, 'mt4')
        jti = _parse_jwt(token)['jti']
        stale = _insert_stale_tab(user['id'], jti)
        fresh = _heartbeat(client, token)
        assert _status(client, user['id']) == 'online'
        client.s.headers.update({'Authorization': f'Bearer {token}'})
        client.post('/presence/close', json={'tab_id': fresh})
        assert _status(client, user['id']) == 'AFK'

    def test_close_all_tabs_is_offline(self, client):
        """Close every tab → offline."""
        user, token = _register(client, 'mt5')
        tab1 = _heartbeat(client, token)
        tab2 = _heartbeat(client, token)
        client.s.headers.update({'Authorization': f'Bearer {token}'})
        client.post('/presence/close', json={'tab_id': tab1})
        client.post('/presence/close', json={'tab_id': tab2})
        assert _status(client, user['id']) == 'offline'

    def test_three_tabs_mixed_freshness(self, client):
        """2 stale + 1 fresh → online."""
        user, token = _register(client, 'mt6')
        jti = _parse_jwt(token)['jti']
        _insert_stale_tab(user['id'], jti, tab_id='s1-' + uuid.uuid4().hex[:6])
        _insert_stale_tab(user['id'], jti, tab_id='s2-' + uuid.uuid4().hex[:6])
        _heartbeat(client, token)
        assert _status(client, user['id']) == 'online'


# ═══════════════════════════════════════════════════════════════════════
# 3. Batch presence (GET /presence?ids=...)
# ═══════════════════════════════════════════════════════════════════════

class TestBatchPresence:
    """GET /presence?ids=... — returns correct statuses for multiple users."""

    def test_all_three_states(self, client):
        """One online, one AFK, one offline in a single batch request."""
        u_on, t_on = _register(client, 'bon')
        u_afk, t_afk = _register(client, 'bafk')
        u_off, t_off = _register(client, 'boff')

        _heartbeat(client, t_on)
        jti_afk = _parse_jwt(t_afk)['jti']
        _insert_stale_tab(u_afk['id'], jti_afk)
        # u_off: no heartbeat

        statuses = _batch_status(client, u_on['id'], u_afk['id'], u_off['id'])
        assert statuses[str(u_on['id'])] == 'online'
        assert statuses[str(u_afk['id'])] == 'AFK'
        assert statuses[str(u_off['id'])] == 'offline'

    def test_empty_ids(self, client):
        """Empty ids parameter returns empty statuses dict."""
        r = client.get('/presence?ids=')
        assert r.status_code == 200
        assert r.json()['statuses'] == {}

    def test_no_ids_param(self, client):
        """No ids parameter at all returns empty statuses dict."""
        r = client.get('/presence')
        assert r.status_code == 200
        assert r.json()['statuses'] == {}

    def test_nonexistent_user_is_offline(self, client):
        """A user id that has never registered returns offline."""
        statuses = _batch_status(client, 999999999)
        assert statuses.get('999999999') == 'offline'

    def test_duplicate_ids(self, client):
        """Duplicate ids don't break the endpoint."""
        user, token = _register(client, 'bdup')
        _heartbeat(client, token)
        statuses = _batch_status(client, user['id'], user['id'])
        assert statuses[str(user['id'])] == 'online'

    def test_single_user_batch(self, client):
        """Batch with one id matches single-user endpoint."""
        user, token = _register(client, 'bsingle')
        _heartbeat(client, token)
        single = _status(client, user['id'])
        batch = _batch_status(client, user['id'])
        assert batch[str(user['id'])] == single

    def test_batch_consistency_with_single(self, client):
        """Batch results must agree with individual lookups for 3 users."""
        users_tokens = [_register(client, f'bcons{i}') for i in range(3)]
        # user 0: online
        _heartbeat(client, users_tokens[0][1])
        # user 1: AFK
        jti1 = _parse_jwt(users_tokens[1][1])['jti']
        _insert_stale_tab(users_tokens[1][0]['id'], jti1)
        # user 2: offline (no heartbeat)

        ids = [u['id'] for u, _ in users_tokens]
        batch = _batch_status(client, *ids)
        for u, _ in users_tokens:
            single = _status(client, u['id'])
            assert batch[str(u['id'])] == single, (
                f"user {u['id']}: batch={batch[str(u['id'])]} vs single={single}"
            )


# ═══════════════════════════════════════════════════════════════════════
# 4. Heartbeat edge cases & error handling
# ═══════════════════════════════════════════════════════════════════════

class TestHeartbeatEdgeCases:
    """POST /presence/heartbeat — validation and edge cases."""

    def test_missing_tab_id_returns_400(self, client):
        """Heartbeat without tab_id should return 400."""
        user, token = _register(client, 'hberr1')
        jti = _parse_jwt(token)['jti']
        r = client.post(
            '/presence/heartbeat',
            headers={'Authorization': f'Bearer {token}'},
            json={'jti': jti},
        )
        assert r.status_code == 400

    def test_missing_auth_returns_401(self, client):
        """Heartbeat without any authentication returns 401."""
        r = client.post(
            '/presence/heartbeat',
            json={'tab_id': 'tab-noauth', 'jti': 'fake'},
        )
        assert r.status_code == 401

    def test_repeated_heartbeats_update_last_active(self, client):
        """Multiple heartbeats on the same tab_id update last_active, not create dupes."""
        user, token = _register(client, 'hbrep')
        tab = _heartbeat(client, token)
        time.sleep(1)
        _heartbeat(client, token, tab_id=tab)
        assert _status(client, user['id']) == 'online'
        # verify only 1 row for that tab
        conn = sqlite3.connect(_db_path())
        try:
            cnt = conn.execute(
                'SELECT COUNT(*) FROM tab_presence WHERE tab_id = ?', (tab,)
            ).fetchone()[0]
            assert cnt == 1
        finally:
            conn.close()

    def test_close_nonexistent_tab_is_ok(self, client):
        """Closing a tab that doesn't exist should succeed (idempotent)."""
        user, token = _register(client, 'hbcl')
        client.s.headers.update({'Authorization': f'Bearer {token}'})
        r = client.post('/presence/close', json={'tab_id': 'nonexistent-tab'})
        assert r.status_code == 200

    def test_close_without_tab_id_returns_400(self, client):
        """POST /presence/close without tab_id returns 400."""
        user, token = _register(client, 'hbcl2')
        client.s.headers.update({'Authorization': f'Bearer {token}'})
        r = client.post('/presence/close', json={})
        assert r.status_code == 400


# ═══════════════════════════════════════════════════════════════════════
# 5. Transition sequences
# ═══════════════════════════════════════════════════════════════════════

class TestTransitionSequences:
    """Full lifecycle transitions: offline → online → AFK → online → offline."""

    @_needs_fast_afk
    def test_full_lifecycle(self, client):
        """offline → online → AFK → online → offline."""
        user, token = _register(client, 'lc')
        uid = user['id']

        # 1. starts offline
        assert _status(client, uid) == 'offline'

        # 2. heartbeat → online
        tab = _heartbeat(client, token)
        assert _status(client, uid) == 'online'

        # 3. wait → AFK
        time.sleep(6)
        assert _status(client, uid) == 'AFK'

        # 4. re-heartbeat → back to online
        _heartbeat(client, token, tab_id=tab)
        assert _status(client, uid) == 'online'

        # 5. close tab → offline
        client.s.headers.update({'Authorization': f'Bearer {token}'})
        client.post('/presence/close', json={'tab_id': tab})
        assert _status(client, uid) == 'offline'

    def test_offline_to_online_multiple_tabs(self, client):
        """Opening multiple tabs brings a user online, closing all returns offline."""
        user, token = _register(client, 'lc2')
        uid = user['id']

        assert _status(client, uid) == 'offline'
        tab1 = _heartbeat(client, token)
        tab2 = _heartbeat(client, token)
        assert _status(client, uid) == 'online'

        client.s.headers.update({'Authorization': f'Bearer {token}'})
        client.post('/presence/close', json={'tab_id': tab1})
        assert _status(client, uid) == 'online'  # tab2 still open

        client.post('/presence/close', json={'tab_id': tab2})
        assert _status(client, uid) == 'offline'

    def test_afk_to_offline_via_close(self, client):
        """AFK user who closes all tabs goes directly to offline."""
        user, token = _register(client, 'lc3')
        jti = _parse_jwt(token)['jti']
        tab = _insert_stale_tab(user['id'], jti)
        assert _status(client, user['id']) == 'AFK'

        client.s.headers.update({'Authorization': f'Bearer {token}'})
        client.post('/presence/close', json={'tab_id': tab})
        assert _status(client, user['id']) == 'offline'


# ═══════════════════════════════════════════════════════════════════════
# 6. /rooms/members-online status field
# ═══════════════════════════════════════════════════════════════════════

class TestRoomMembersOnlineStatus:
    """/rooms/members-online now returns a 'status' field per member."""

    def _create_room_with_members(self, client, owner_token, member_tokens):
        """Create a room and add members. Returns the room id."""
        client.s.headers.update({'Authorization': f'Bearer {owner_token}'})
        r = client.post('/rooms', json={'name': 'room-' + uuid.uuid4().hex[:6]})
        assert r.status_code == 200
        room_id = r.json()['room']['id']
        for mt in member_tokens:
            client.s.headers.update({'Authorization': f'Bearer {owner_token}'})
            # invite the member (add them to the room)
            jti = _parse_jwt(mt)
            client.post(f'/rooms/{room_id}/members/add', json={'user_id': jti.get('id', 0)})
        return room_id

    def test_status_field_present(self, client):
        """Each member in /rooms/members-online has a 'status' field."""
        user, token = _register(client, 'rms1')
        client.s.headers.update({'Authorization': f'Bearer {token}'})
        # create a room
        r = client.post('/rooms', json={'name': 'statusroom-' + uuid.uuid4().hex[:6]})
        assert r.status_code == 200
        room_id = r.json()['room']['id']
        # heartbeat so the owner is online
        _heartbeat(client, token)
        # fetch members-online
        client.s.headers.update({'Authorization': f'Bearer {token}'})
        res = client.get('/rooms/members-online')
        assert res.status_code == 200
        rooms = res.json()['rooms']
        my_room = [rm for rm in rooms if rm['id'] == room_id]
        assert len(my_room) == 1
        for m in my_room[0]['members']:
            assert 'status' in m, f"member {m} missing 'status' field"
            assert m['status'] in ('online', 'AFK', 'offline')
            # also has legacy 'online' boolean
            assert 'online' in m

    def test_status_values_online_afk_offline(self, client):
        """Room with 3 members: one online, one AFK, one offline → correct status."""
        u_on, t_on = _register(client, 'rmo1')
        u_afk, t_afk = _register(client, 'rmo2')
        u_off, t_off = _register(client, 'rmo3')

        # create room as u_on, add the others
        client.s.headers.update({'Authorization': f'Bearer {t_on}'})
        r = client.post('/rooms', json={'name': 'mixed-' + uuid.uuid4().hex[:6]})
        assert r.status_code == 200
        room_id = r.json()['room']['id']
        client.post(f'/rooms/{room_id}/members/add', json={'user_id': u_afk['id']})
        client.post(f'/rooms/{room_id}/members/add', json={'user_id': u_off['id']})

        # u_on → online
        _heartbeat(client, t_on)
        # u_afk → AFK (stale tab)
        jti_afk = _parse_jwt(t_afk)['jti']
        _insert_stale_tab(u_afk['id'], jti_afk)
        # u_off → no heartbeat

        client.s.headers.update({'Authorization': f'Bearer {t_on}'})
        res = client.get('/rooms/members-online')
        assert res.status_code == 200
        my_room = [rm for rm in res.json()['rooms'] if rm['id'] == room_id]
        assert len(my_room) == 1
        members = {m['id']: m for m in my_room[0]['members']}

        assert members[u_on['id']]['status'] == 'online'
        assert members[u_on['id']]['online'] is True

        assert members[u_afk['id']]['status'] == 'AFK'
        assert members[u_afk['id']]['online'] is False

        assert members[u_off['id']]['status'] == 'offline'
        assert members[u_off['id']]['online'] is False

    def test_members_sorted_online_afk_offline(self, client):
        """Members are sorted: online first, then AFK, then offline."""
        u_on, t_on = _register(client, 'sort1')
        u_afk, t_afk = _register(client, 'sort2')
        u_off, t_off = _register(client, 'sort3')

        client.s.headers.update({'Authorization': f'Bearer {t_on}'})
        r = client.post('/rooms', json={'name': 'sortroom-' + uuid.uuid4().hex[:6]})
        assert r.status_code == 200
        room_id = r.json()['room']['id']
        client.post(f'/rooms/{room_id}/members/add', json={'user_id': u_afk['id']})
        client.post(f'/rooms/{room_id}/members/add', json={'user_id': u_off['id']})

        _heartbeat(client, t_on)
        jti_afk = _parse_jwt(t_afk)['jti']
        _insert_stale_tab(u_afk['id'], jti_afk)

        client.s.headers.update({'Authorization': f'Bearer {t_on}'})
        res = client.get('/rooms/members-online')
        my_room = [rm for rm in res.json()['rooms'] if rm['id'] == room_id][0]
        status_order = [m['status'] for m in my_room['members']]
        # verify ordering: all online before AFK before offline
        expected_order = {'online': 0, 'AFK': 1, 'offline': 2}
        numeric = [expected_order.get(s, 9) for s in status_order]
        assert numeric == sorted(numeric), f'bad order: {status_order}'


# ═══════════════════════════════════════════════════════════════════════
# 7. Concurrent / cross-user independence
# ═══════════════════════════════════════════════════════════════════════

class TestCrossUserIndependence:
    """One user's heartbeats must not affect another user's status."""

    def test_other_user_heartbeat_no_effect(self, client):
        """User A's heartbeat does not make User B online."""
        a, ta = _register(client, 'indA')
        b, tb = _register(client, 'indB')
        _heartbeat(client, ta)
        assert _status(client, a['id']) == 'online'
        assert _status(client, b['id']) == 'offline'

    def test_closing_other_user_tab_no_effect(self, client):
        """Closing user A's tab does not change user B's status."""
        a, ta = _register(client, 'indC')
        b, tb = _register(client, 'indD')
        tab_a = _heartbeat(client, ta)
        _heartbeat(client, tb)
        assert _status(client, b['id']) == 'online'
        client.s.headers.update({'Authorization': f'Bearer {ta}'})
        client.post('/presence/close', json={'tab_id': tab_a})
        assert _status(client, b['id']) == 'online'
        assert _status(client, a['id']) == 'offline'


# ═══════════════════════════════════════════════════════════════════════
# 8. Legacy boolean 'online' field backward compatibility
# ═══════════════════════════════════════════════════════════════════════

class TestLegacyOnlineBoolean:
    """The legacy 'online' boolean in /rooms/members-online must remain correct."""

    def test_online_true_when_status_online(self, client):
        user, token = _register(client, 'legon')
        client.s.headers.update({'Authorization': f'Bearer {token}'})
        client.post('/rooms', json={'name': 'legroom-' + uuid.uuid4().hex[:6]})
        _heartbeat(client, token)
        res = client.get('/rooms/members-online')
        rooms = res.json()['rooms']
        for rm in rooms:
            for m in rm['members']:
                if m['id'] == user['id']:
                    assert m['online'] is True
                    assert m['status'] == 'online'

    def test_online_false_when_afk(self, client):
        user, token = _register(client, 'legafk')
        jti = _parse_jwt(token)['jti']
        client.s.headers.update({'Authorization': f'Bearer {token}'})
        client.post('/rooms', json={'name': 'legroom2-' + uuid.uuid4().hex[:6]})
        _insert_stale_tab(user['id'], jti)
        res = client.get('/rooms/members-online')
        rooms = res.json()['rooms']
        for rm in rooms:
            for m in rm['members']:
                if m['id'] == user['id']:
                    assert m['online'] is False
                    assert m['status'] == 'AFK'

    def test_online_false_when_offline(self, client):
        user, token = _register(client, 'legoff')
        client.s.headers.update({'Authorization': f'Bearer {token}'})
        client.post('/rooms', json={'name': 'legroom3-' + uuid.uuid4().hex[:6]})
        _delete_all_tabs(user['id'])
        res = client.get('/rooms/members-online')
        rooms = res.json()['rooms']
        for rm in rooms:
            for m in rm['members']:
                if m['id'] == user['id']:
                    assert m['online'] is False
                    assert m['status'] == 'offline'
