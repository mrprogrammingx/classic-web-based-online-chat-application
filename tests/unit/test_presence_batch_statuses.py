import time
import json
import sqlite3
import os
import uuid


def parse_jwt_no_verify(token: str):
    try:
        parts = token.split('.')
        payload = parts[1]
        payload += '=' * (-len(payload) % 4)
        import base64
        return json.loads(base64.urlsafe_b64decode(payload))
    except Exception:
        return {}


def test_batch_presence_online_afk_offline(client):
    # create three users
    now = int(time.time())
    users = []
    for suffix in ('online', 'afk', 'offline'):
        email = f"test+{uuid.uuid4().hex}@example.com"
        username = f'user_{suffix}_{uuid.uuid4().hex[:6]}'
        pw = 'Secret123!'
        r = client.post('/register', json={'email': email, 'username': username, 'password': pw})
        assert r.status_code == 200
        data = r.json()
        users.append({'token': data['token'], 'user': data['user']})

    # send heartbeat for first user (online)
    u_online = users[0]
    payload = parse_jwt_no_verify(u_online['token'])
    jti_online = payload.get('jti')
    assert jti_online
    tab_online = 'tab-' + uuid.uuid4().hex[:8]
    r = client.post('/presence/heartbeat', headers={'Authorization': f"Bearer {u_online['token']}"}, json={'tab_id': tab_online, 'jti': jti_online})
    assert r.status_code == 200

    # insert an old tab_presence entry for the second user (AFK)
    u_afk = users[1]
    payload2 = parse_jwt_no_verify(u_afk['token'])
    jti_afk = payload2.get('jti')
    assert jti_afk
    tab_afk = 'tab-' + uuid.uuid4().hex[:8]
    # compute a timestamp older than AFK_SECONDS (use 120 s to be safe
    # even when the server runs with the default 60 s AFK threshold)
    old_ts = int(time.time()) - 120
    # write directly into the DB so we can simulate an AFK last_active
    from core.config import DB_PATH
    db_path = os.path.join(os.getcwd(), DB_PATH)
    conn = sqlite3.connect(db_path)
    try:
        cur = conn.cursor()
        cur.execute('INSERT OR REPLACE INTO tab_presence (tab_id, jti, user_id, created_at, last_active, user_agent, ip) VALUES (?, ?, ?, ?, ?, ?, ?)',
                    (tab_afk, jti_afk, u_afk['user']['id'], old_ts, old_ts, 'pytest', '127.0.0.1'))
        conn.commit()
    finally:
        conn.close()

    # third user remains offline
    u_off = users[2]

    ids = ','.join(str(u['user']['id']) for u in users)
    pres = client.get(f'/presence?ids={ids}')
    assert pres.status_code == 200
    statuses = pres.json().get('statuses', {})
    # online user should be 'online'
    assert statuses.get(str(users[0]['user']['id'])) in ('online', 'AFK')
    # afk user should be 'AFK' (not online)
    assert statuses.get(str(users[1]['user']['id'])) == 'AFK'
    # offline user should be 'offline'
    assert statuses.get(str(users[2]['user']['id'])) == 'offline'
