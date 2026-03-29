"""Presence smoke tests — quick API-level health checks.

These are lightweight tests that verify the presence system's core contracts
without expensive sleeps. They are designed to run fast and catch regressions
in heartbeat / close / status / batch / rooms-members-online endpoints.

Meant to be run as part of CI or a manual quick-check:
    pytest tests/unit/test_presence_smoke.py -v
"""

import base64
import json
import os
import sqlite3
import time
import uuid


# ── helpers ──────────────────────────────────────────────────────────────

def _parse_jwt(token: str) -> dict:
    parts = token.split('.')
    payload = parts[1] + '=' * (-len(parts[1]) % 4)
    return json.loads(base64.urlsafe_b64decode(payload))


def _register(client, prefix='sm'):
    suffix = uuid.uuid4().hex[:8]
    email = f'{prefix}_{suffix}@example.com'
    username = f'{prefix}_{suffix}'
    r = client.post('/register', json={'email': email, 'username': username, 'password': 'pw'})
    assert r.status_code == 200, f'register failed: {r.text}'
    data = r.json()
    return data['user'], data['token']


def _heartbeat(client, token, tab_id=None):
    jti = _parse_jwt(token).get('jti')
    if tab_id is None:
        tab_id = 'tab-' + uuid.uuid4().hex[:8]
    r = client.post(
        '/presence/heartbeat',
        headers={'Authorization': f'Bearer {token}'},
        json={'tab_id': tab_id, 'jti': jti},
    )
    assert r.status_code == 200, f'heartbeat failed: {r.text}'
    return tab_id


def _status(client, user_id):
    r = client.get(f'/presence/{user_id}')
    assert r.status_code == 200
    return r.json()['status']


def _batch_status(client, *user_ids):
    ids = ','.join(str(uid) for uid in user_ids)
    r = client.get(f'/presence?ids={ids}')
    assert r.status_code == 200
    return r.json().get('statuses', {})


def _db_path():
    from core.config import DB_PATH
    return os.path.join(os.getcwd(), DB_PATH)


def _insert_stale_tab(user_id, jti, tab_id=None, age_extra=120):
    """Insert a stale tab.  We use age_extra=120 by default so the row is
    well past the AFK threshold regardless of server config (the server
    enforces min 5 s in test-mode and defaults to 60 s otherwise)."""
    if tab_id is None:
        tab_id = 'tab-stale-' + uuid.uuid4().hex[:8]
    old_ts = int(time.time()) - age_extra
    conn = sqlite3.connect(_db_path())
    try:
        conn.execute(
            'INSERT OR REPLACE INTO tab_presence '
            '(tab_id, jti, user_id, created_at, last_active, user_agent, ip) '
            'VALUES (?, ?, ?, ?, ?, ?, ?)',
            (tab_id, jti, user_id, old_ts, old_ts, 'smoke-test', '127.0.0.1'),
        )
        conn.commit()
    finally:
        conn.close()
    return tab_id


# ═══════════════════════════════════════════════════════════════════════
# Smoke: heartbeat → online
# ═══════════════════════════════════════════════════════════════════════

class TestPresenceSmoke:
    """Quick health-check tests that run in < 1 s each (no sleeps)."""

    def test_heartbeat_sets_online(self, client):
        """Heartbeat immediately results in online status."""
        user, token = _register(client, 'smkon')
        _heartbeat(client, token)
        assert _status(client, user['id']) == 'online'

    def test_close_tab_sets_offline(self, client):
        """Close the only tab → offline."""
        user, token = _register(client, 'smkoff')
        tab = _heartbeat(client, token)
        assert _status(client, user['id']) == 'online'
        client.s.headers.update({'Authorization': f'Bearer {token}'})
        r = client.post('/presence/close', json={'tab_id': tab})
        assert r.status_code == 200
        assert _status(client, user['id']) == 'offline'

    def test_stale_tab_is_afk(self, client):
        """A user with only stale tab rows is AFK."""
        user, token = _register(client, 'smkafk')
        jti = _parse_jwt(token)['jti']
        _insert_stale_tab(user['id'], jti)
        assert _status(client, user['id']) == 'AFK'

    def test_no_heartbeat_is_offline(self, client):
        """A user who never sent a heartbeat is offline."""
        user, token = _register(client, 'smknew')
        assert _status(client, user['id']) == 'offline'

    def test_batch_returns_correct_states(self, client):
        """Batch endpoint agrees with individual lookups."""
        u1, t1 = _register(client, 'smkb1')
        u2, t2 = _register(client, 'smkb2')
        u3, t3 = _register(client, 'smkb3')

        _heartbeat(client, t1)  # online
        jti2 = _parse_jwt(t2)['jti']
        _insert_stale_tab(u2['id'], jti2)  # AFK
        # u3 — no heartbeat → offline

        batch = _batch_status(client, u1['id'], u2['id'], u3['id'])
        assert batch[str(u1['id'])] == 'online'
        assert batch[str(u2['id'])] == 'AFK'
        assert batch[str(u3['id'])] == 'offline'

    def test_rooms_members_online_has_status_field(self, client):
        """GET /rooms/members-online returns a status field per member."""
        user, token = _register(client, 'smkrm')
        client.s.headers.update({'Authorization': f'Bearer {token}'})
        r = client.post('/rooms', json={'name': 'smoke-room-' + uuid.uuid4().hex[:6]})
        assert r.status_code == 200
        room_id = r.json()['room']['id']

        _heartbeat(client, token)

        client.s.headers.update({'Authorization': f'Bearer {token}'})
        res = client.get('/rooms/members-online')
        assert res.status_code == 200
        rooms = res.json()['rooms']
        my_room = [rm for rm in rooms if rm['id'] == room_id]
        assert len(my_room) == 1
        for m in my_room[0]['members']:
            assert 'status' in m
            assert m['status'] in ('online', 'AFK', 'offline')
            assert 'online' in m  # legacy boolean


# ═══════════════════════════════════════════════════════════════════════
# Smoke: multi-tab rule — active in ≥1 tab → online
# ═══════════════════════════════════════════════════════════════════════

class TestMultiTabSmoke:
    """Key invariant: if the user is active in at least one tab, they
    appear as online to others — regardless of how many stale tabs exist."""

    def test_one_fresh_among_stale_is_online(self, client):
        """3 stale tabs + 1 fresh tab → online (not AFK)."""
        user, token = _register(client, 'mtsmk')
        jti = _parse_jwt(token)['jti']
        # insert 3 stale tabs
        for i in range(3):
            _insert_stale_tab(user['id'], jti, tab_id=f'stale-{i}-{uuid.uuid4().hex[:6]}')
        assert _status(client, user['id']) == 'AFK'  # sanity

        # now one fresh heartbeat
        _heartbeat(client, token)
        assert _status(client, user['id']) == 'online'

    def test_two_fresh_tabs_is_online(self, client):
        """Two fresh tabs → online."""
        user, token = _register(client, 'mtsmk2')
        _heartbeat(client, token)
        _heartbeat(client, token)
        assert _status(client, user['id']) == 'online'

    def test_close_one_of_two_fresh_stays_online(self, client):
        """Closing one of two fresh tabs → still online."""
        user, token = _register(client, 'mtsmk3')
        tab1 = _heartbeat(client, token)
        tab2 = _heartbeat(client, token)
        client.s.headers.update({'Authorization': f'Bearer {token}'})
        client.post('/presence/close', json={'tab_id': tab1})
        assert _status(client, user['id']) == 'online'

    def test_close_all_tabs_goes_offline(self, client):
        """Closing every tab → offline (not AFK)."""
        user, token = _register(client, 'mtsmk4')
        tab1 = _heartbeat(client, token)
        tab2 = _heartbeat(client, token)
        client.s.headers.update({'Authorization': f'Bearer {token}'})
        client.post('/presence/close', json={'tab_id': tab1})
        client.post('/presence/close', json={'tab_id': tab2})
        assert _status(client, user['id']) == 'offline'

    def test_re_heartbeat_recovers_from_afk(self, client):
        """User who was AFK sends fresh heartbeat → back to online."""
        user, token = _register(client, 'mtsmk5')
        jti = _parse_jwt(token)['jti']
        stale_tab = _insert_stale_tab(user['id'], jti)
        assert _status(client, user['id']) == 'AFK'
        # re-heartbeat on same tab
        _heartbeat(client, token, tab_id=stale_tab)
        assert _status(client, user['id']) == 'online'


# ═══════════════════════════════════════════════════════════════════════
# Smoke: room members sorting
# ═══════════════════════════════════════════════════════════════════════

class TestRoomMembersSortSmoke:
    """Members in /rooms/members-online are sorted: online → AFK → offline."""

    def test_sort_order(self, client):
        u_on, t_on = _register(client, 'srtOn')
        u_afk, t_afk = _register(client, 'srtAfk')
        u_off, t_off = _register(client, 'srtOff')

        # create room, add others
        client.s.headers.update({'Authorization': f'Bearer {t_on}'})
        r = client.post('/rooms', json={'name': 'sort-smoke-' + uuid.uuid4().hex[:6]})
        assert r.status_code == 200
        room_id = r.json()['room']['id']
        client.post(f'/rooms/{room_id}/members/add', json={'user_id': u_afk['id']})
        client.post(f'/rooms/{room_id}/members/add', json={'user_id': u_off['id']})

        # u_on: heartbeat → online
        _heartbeat(client, t_on)
        # u_afk: stale tab → AFK
        jti_afk = _parse_jwt(t_afk)['jti']
        _insert_stale_tab(u_afk['id'], jti_afk)
        # u_off: no heartbeat → offline

        client.s.headers.update({'Authorization': f'Bearer {t_on}'})
        res = client.get('/rooms/members-online')
        assert res.status_code == 200
        my_room = [rm for rm in res.json()['rooms'] if rm['id'] == room_id]
        assert len(my_room) == 1
        statuses = [m['status'] for m in my_room[0]['members']]
        order_map = {'online': 0, 'AFK': 1, 'offline': 2}
        numeric = [order_map.get(s, 9) for s in statuses]
        assert numeric == sorted(numeric), f'bad sort order: {statuses}'


# ═══════════════════════════════════════════════════════════════════════
# Smoke: error handling
# ═══════════════════════════════════════════════════════════════════════

class TestErrorSmoke:
    """Quick validation of error responses."""

    def test_heartbeat_no_auth_401(self, client):
        r = client.post('/presence/heartbeat', json={'tab_id': 'x', 'jti': 'y'})
        assert r.status_code == 401

    def test_heartbeat_no_tab_id_400(self, client):
        user, token = _register(client, 'smkerr')
        r = client.post(
            '/presence/heartbeat',
            headers={'Authorization': f'Bearer {token}'},
            json={'jti': _parse_jwt(token)['jti']},
        )
        assert r.status_code == 400

    def test_close_no_tab_id_400(self, client):
        user, token = _register(client, 'smkerr2')
        client.s.headers.update({'Authorization': f'Bearer {token}'})
        r = client.post('/presence/close', json={})
        assert r.status_code == 400

    def test_batch_empty_ids_returns_empty(self, client):
        r = client.get('/presence?ids=')
        assert r.status_code == 200
        assert r.json()['statuses'] == {}

    def test_nonexistent_user_is_offline(self, client):
        assert _status(client, 999999999) == 'offline'


# ═══════════════════════════════════════════════════════════════════════
# Smoke: cross-user isolation
# ═══════════════════════════════════════════════════════════════════════

class TestCrossUserSmoke:
    """One user's presence actions never leak to another user."""

    def test_heartbeat_doesnt_affect_other(self, client):
        a, ta = _register(client, 'isoa')
        b, tb = _register(client, 'isob')
        _heartbeat(client, ta)
        assert _status(client, a['id']) == 'online'
        assert _status(client, b['id']) == 'offline'

    def test_close_doesnt_affect_other(self, client):
        a, ta = _register(client, 'isoc')
        b, tb = _register(client, 'isod')
        tab_a = _heartbeat(client, ta)
        _heartbeat(client, tb)
        client.s.headers.update({'Authorization': f'Bearer {ta}'})
        client.post('/presence/close', json={'tab_id': tab_a})
        assert _status(client, a['id']) == 'offline'
        assert _status(client, b['id']) == 'online'
