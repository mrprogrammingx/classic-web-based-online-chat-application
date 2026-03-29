"""
Integration test: Simulating the user's scenario.

User opens a browser, becomes online, then closes all tabs.
Without cleanup, tabs would remain in DB showing "AFK".
With cleanup, tabs get removed and user shows "offline".
"""

import pytest
import time
import aiosqlite
from core.utils import (
    touch_tab, get_presence_status, cleanup_stale_tabs
)
import db as db_mod


@pytest.mark.asyncio
async def test_user_tabs_closed_scenario():
    """
    Simulate user closing all tabs.
    
    1. User logs in, heartbeat touches a tab (tab is "recent")
    2. User closes browser without cleanup yet (tab is still in DB)
    3. Without cleanup: tab is still there, shows AFK if old enough, online if recent
    4. With cleanup: stale tabs are removed, user shows offline
    """
    user_id = 8888
    jti = 'jti-scenario-001'
    
    # Scenario 1: User just opened a tab (simulate login heartbeat)
    tab_id_1 = f'tab-scenario-001-{int(time.time())}'
    now = int(time.time())
    
    async with aiosqlite.connect(db_mod.DB) as db:
        await db.execute(
            'INSERT INTO tab_presence (tab_id, jti, user_id, created_at, last_active) VALUES (?, ?, ?, ?, ?)',
            (tab_id_1, jti, user_id, now, now)
        )
        await db.commit()
    
    # User should be online (tab is recent)
    status = await get_presence_status(user_id)
    assert status == 'online', f"Freshly opened tab should show user as online, got {status}"
    
    # Scenario 2: User closes browser without sending close signal
    # Simulate tab not being touched for 30 hours (overnight + next morning)
    stale_time = now - (86400 + 3600 + 3600)  # 30 hours ago
    
    async with aiosqlite.connect(db_mod.DB) as db:
        # Manually backdate the tab to simulate it being closed
        await db.execute(
            'UPDATE tab_presence SET last_active = ? WHERE tab_id = ?',
            (stale_time, tab_id_1)
        )
        await db.commit()
        
        # Verify tab exists but is stale
        cur = await db.execute(
            'SELECT COUNT(*) FROM tab_presence WHERE user_id = ? AND last_active < ?',
            (user_id, now - 86400)
        )
        stale_count = (await cur.fetchone())[0]
        assert stale_count == 1, "Tab should be stale (older than 24 hours)"
    
    # Scenario 3: Without cleanup, tab might still show as AFK (depending on AFK_SECONDS)
    # But with cleanup enabled, get_presence_status will clean up and show offline
    status = await get_presence_status(user_id)
    assert status == 'offline', f"After cleanup of stale tabs, user should be offline, got {status}"
    
    # Verify tab was actually removed by cleanup
    async with aiosqlite.connect(db_mod.DB) as db:
        cur = await db.execute(
            'SELECT COUNT(*) FROM tab_presence WHERE tab_id = ?',
            (tab_id_1,)
        )
        count = (await cur.fetchone())[0]
        assert count == 0, "Stale tab should have been cleaned up"


@pytest.mark.asyncio
async def test_multiple_tabs_mixed_freshness():
    """
    User has multiple tabs open.
    One tab is active (recent), one is stale.
    User should show online (at least one active tab).
    After cleanup, stale tabs removed but active tabs preserved.
    """
    user_id = 8887
    jti = f'jti-scenario-002-{int(time.time())}'
    now = int(time.time())
    
    # Clean up any leftover tabs for this user from previous runs
    async with aiosqlite.connect(db_mod.DB) as db:
        await db.execute('DELETE FROM tab_presence WHERE user_id = ?', (user_id,))
        await db.commit()
    
    # Tab 1: Recent (active within last 60 seconds, default AFK threshold)
    # Use a very recent time (1 second ago) to be safe
    tab_id_recent = f'tab-active-recent-8887-{now}'
    recent_time = now - 1  # 1 second ago (very recent, definitely within AFK threshold)
    
    # Tab 2: Stale (closed without signal)
    tab_id_stale = f'tab-stale-old-8887-{now}-old'
    stale_time = now - (86400 + 3600)  # 25 hours ago
    
    async with aiosqlite.connect(db_mod.DB) as db:
        await db.execute(
            'INSERT INTO tab_presence (tab_id, jti, user_id, created_at, last_active) VALUES (?, ?, ?, ?, ?)',
            (tab_id_recent, jti, user_id, recent_time, recent_time)
        )
        await db.execute(
            'INSERT INTO tab_presence (tab_id, jti, user_id, created_at, last_active) VALUES (?, ?, ?, ?, ?)',
            (tab_id_stale, jti, user_id, stale_time, stale_time)
        )
        await db.commit()
        
        # Verify both tabs were inserted
        cur = await db.execute(
            'SELECT COUNT(*) FROM tab_presence WHERE user_id = ?',
            (user_id,)
        )
        count_before = (await cur.fetchone())[0]
        assert count_before == 2, f"Should have 2 tabs before cleanup, got {count_before}"
    
    # User should be online (at least one active tab)
    status = await get_presence_status(user_id)
    assert status == 'online', f"User with active tab should be online, got {status}"
    
    # Verify cleanup removed stale tab but kept active one
    async with aiosqlite.connect(db_mod.DB) as db:
        cur = await db.execute(
            'SELECT COUNT(*) FROM tab_presence WHERE user_id = ?',
            (user_id,)
        )
        count = (await cur.fetchone())[0]
        assert count == 1, f"Only active tab should remain after cleanup, but found {count}"
        
        # Verify the remaining tab is the recent one
        cur = await db.execute(
            'SELECT tab_id FROM tab_presence WHERE user_id = ?',
            (user_id,)
        )
        remaining_tab = (await cur.fetchone())[0]
        assert remaining_tab == tab_id_recent, f"Remaining tab should be the active one, got {remaining_tab}"
