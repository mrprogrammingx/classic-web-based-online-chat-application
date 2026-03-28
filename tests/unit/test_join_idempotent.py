import uuid
import sqlite3
import time
from core.config import DB_PATH as DB


def _reg_and_token(client, prefix='user'):
    suffix = str(uuid.uuid4())[:8]
    email = f'{prefix}_{suffix}@example.com'
    username = f'{prefix}_{suffix}'
    r = client.post('/register', json={'email': email, 'username': username, 'password': 'pass'})
    assert r.status_code == 200
    return r.json()['user'], r.json()['token']


def test_join_is_idempotent(client):
    owner, owner_token = _reg_and_token(client, 'owner')
    client.s.headers.update({'Authorization': f'Bearer {owner_token}'})
    rn = f"room_{str(uuid.uuid4())[:8]}"
    r = client.post('/rooms', json={'name': rn, 'visibility': 'public'})
    assert r.status_code == 200
    room = r.json().get('room') or r.json().get('id')
    # locate room id
    resp = client.get('/rooms')
    rooms = resp.json().get('rooms', [])
    created = [x for x in rooms if x.get('name') == rn]
    assert created
    rid = created[0]['id']

    # create a joiner and perform join twice
    joiner, joiner_token = _reg_and_token(client, 'joiner')
    client.s.headers.update({'Authorization': f'Bearer {joiner_token}'})
    j1 = client.post(f'/rooms/{rid}/join')
    assert j1.status_code == 200
    j2 = client.post(f'/rooms/{rid}/join')
    assert j2.status_code == 200

    # verify DB contains only one membership row for user/room
    conn = sqlite3.connect(DB)
    cur = conn.cursor()
    cur.execute('SELECT COUNT(*) FROM memberships WHERE room_id = ? AND user_id = ?', (rid, joiner['id']))
    cnt = cur.fetchone()[0]
    conn.close()
    assert cnt == 1
