import uuid
import sqlite3
import time
from core.config import DB_PATH


def test_users_search_orders_by_created_at_desc(client):
    """Register three users with the same prefix, set created_at deterministically
    and assert the /users/search endpoint returns them newest-first.
    """
    unique = uuid.uuid4().hex[:6]
    prefix = f'ord_{unique}'

    def reg(suffix):
        username = f"{prefix}_{suffix}"
        email = f"{username}@example.com"
        r = client.post('/register', json={'email': email, 'username': username, 'password': 'pw'})
        assert r.status_code == 200, r.text
        data = r.json()
        return data['user'], data['token']

    u1, t1 = reg('a')
    u2, t2 = reg('b')
    u3, t3 = reg('c')

    # Overwrite created_at to deterministic values so ordering is reliable
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    try:
        cur.execute('UPDATE users SET created_at = ? WHERE id = ?', (100, u1['id']))
        cur.execute('UPDATE users SET created_at = ? WHERE id = ?', (200, u2['id']))
        cur.execute('UPDATE users SET created_at = ? WHERE id = ?', (300, u3['id']))
        conn.commit()
    finally:
        conn.close()

    # perform search authenticated as u1
    client.s.headers.update({'Authorization': f'Bearer {t1}'})
    res = client.get(f'/users/search?q={prefix}')
    assert res.status_code == 200
    users = res.json().get('users', [])
    # ensure we at least got these three back in newest-first order
    returned_usernames = [u['username'] for u in users if u['username'].startswith(prefix)]
    assert returned_usernames[:3] == [u3['username'], u2['username'], u1['username']]
