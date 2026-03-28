import time
import aiosqlite
import pytest

import core.utils as utils


@pytest.mark.asyncio
async def test_get_presence_statuses_basic(tmp_path, monkeypatch):
    # Create a temporary sqlite DB file and monkeypatch core.utils.DB to point to it
    db_path = str(tmp_path / 'test_presence.db')
    monkeypatch.setattr(utils, 'DB', db_path)
    # make presence cutoff small and deterministic (5s)
    monkeypatch.setattr(utils, 'presence_online_seconds', lambda: 5)

    # Create table and insert rows: user 1 recent, user 2 old
    async with aiosqlite.connect(db_path) as db:
        await db.execute('''CREATE TABLE tab_presence (
            tab_id TEXT PRIMARY KEY,
            jti TEXT NOT NULL,
            user_id INTEGER NOT NULL,
            created_at INTEGER NOT NULL,
            last_active INTEGER NOT NULL,
            user_agent TEXT,
            ip TEXT
        )''')
        # create a minimal sessions table so fallback queries in utils work
        await db.execute('''CREATE TABLE sessions (
            jti TEXT PRIMARY KEY,
            user_id INTEGER NOT NULL,
            created_at INTEGER NOT NULL,
            expires_at INTEGER NOT NULL,
            ip TEXT,
            user_agent TEXT,
            last_active INTEGER
        )''')
        await db.commit()
        now = int(time.time())
        # user 1: one recent tab
        await db.execute('INSERT INTO tab_presence (tab_id, jti, user_id, created_at, last_active) VALUES (?, ?, ?, ?, ?)',
                         ('t-recent', 'jti-r', 1, now, now))
        # user 2: one old tab
        await db.execute('INSERT INTO tab_presence (tab_id, jti, user_id, created_at, last_active) VALUES (?, ?, ?, ?, ?)',
                         ('t-old', 'jti-o', 2, now - 3600, now - 3600))
        await db.commit()

    # Run the function under test
    res = await utils.get_presence_statuses([1, 2, 3])

    # user 1 should be online
    assert res.get('1') == 'online'
    # user 2 should be AFK (has a tab but last_active is older than cutoff)
    assert res.get('2') == 'AFK'
    # user 3 has no tabs -> offline
    assert res.get('3') == 'offline'
