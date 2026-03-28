import os
import time
import asyncio

import aiosqlite


def test_touch_tab_updates_db_direct(tmp_path, monkeypatch):
    """Create a temporary DB, initialize schema, insert a user, call
    core.utils.touch_tab and assert tab_presence was updated.
    This avoids HTTP and directly verifies the DB write.
    """
    db_file = tmp_path / 'test_auth.db'
    monkeypatch.setenv('AUTH_DB_PATH', str(db_file))

    # Import init_db AFTER env override so it uses the tmp DB path
    from db.schema import init_db
    from core.config import DB_PATH

    async def run_test():
        # initialize schema
        await init_db()

        # insert a user to satisfy any FK constraints
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute('INSERT INTO users (email, username, password, created_at) VALUES (?, ?, ?, ?)',
                             ('tuser@example.com', 'tuser', 'pw', int(time.time())))
            await db.commit()
            cur = await db.execute('SELECT id FROM users WHERE email = ?', ('tuser@example.com',))
            row = await cur.fetchone()
            assert row is not None
            user_id = row[0]

        # call the touch_tab helper
        from core.utils import touch_tab
        tab_id = 'test-tab-1'
        await touch_tab(tab_id, 'jti-test-1', user_id)

        # verify tab_presence row exists and last_active is recent
        async with aiosqlite.connect(DB_PATH) as db:
            cur = await db.execute('SELECT tab_id, user_id, last_active, created_at FROM tab_presence WHERE tab_id = ?', (tab_id,))
            prow = await cur.fetchone()
            assert prow is not None, 'tab_presence row not found'
            got_tab_id, got_user_id, last_active, created_at = prow
            assert got_tab_id == tab_id
            assert got_user_id == user_id
            assert abs(int(time.time()) - int(last_active)) < 10, f'last_active not recent: {last_active}'

    asyncio.run(run_test())
