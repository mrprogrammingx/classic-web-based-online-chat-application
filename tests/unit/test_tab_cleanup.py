"""Tests for stale tab cleanup functionality.

When browser tabs are closed without sending an explicit close signal,
their records remain in the database. The cleanup_stale_tabs() function
should remove tabs that haven't been touched for 24+ hours, ensuring
users with all tabs closed show as 'offline'.
"""

import pytest
import time
import aiosqlite
from core.utils import (
    touch_tab, remove_tab, get_presence_status, cleanup_stale_tabs
)
import db as db_mod


@pytest.mark.asyncio
async def test_cleanup_removes_stale_tabs():
    """Verify that cleanup_stale_tabs removes tabs older than 24 hours."""
    user_id = 9991
    tab_id = f'tab-stale-0001-{int(time.time())}'
    jti = f'jti-test-0001-{int(time.time())}'
    
    # Clean up first
    async with aiosqlite.connect(db_mod.DB) as db:
        await db.execute('DELETE FROM tab_presence WHERE user_id = ?', (user_id,))
        await db.commit()
    
    # Insert a tab and manually set its last_active to 25+ hours ago
    now = int(time.time())
    stale_time = now - (86400 + 3600)  # 25 hours ago
    
    async with aiosqlite.connect(db_mod.DB) as db:
        await db.execute(
            'INSERT INTO tab_presence (tab_id, jti, user_id, created_at, last_active) VALUES (?, ?, ?, ?, ?)',
            (tab_id, jti, user_id, stale_time, stale_time)
        )
        await db.commit()
        
        # Verify tab exists
        cur = await db.execute('SELECT COUNT(*) FROM tab_presence WHERE tab_id = ?', (tab_id,))
        count = (await cur.fetchone())[0]
        assert count == 1, "Tab should exist before cleanup"
    
    # Run cleanup with default 24-hour threshold
    await cleanup_stale_tabs()
    
    # Verify tab was removed
    async with aiosqlite.connect(db_mod.DB) as db:
        cur = await db.execute('SELECT COUNT(*) FROM tab_presence WHERE tab_id = ?', (tab_id,))
        count = (await cur.fetchone())[0]
        assert count == 0, "Stale tab should be removed after cleanup"


@pytest.mark.asyncio
async def test_cleanup_preserves_recent_tabs():
    """Verify that cleanup_stale_tabs preserves tabs touched within 24 hours."""
    user_id = 9992
    tab_id = f'tab-recent-0002-{int(time.time())}'
    jti = f'jti-test-recent-0002-{int(time.time())}'
    
    # Clean up first
    async with aiosqlite.connect(db_mod.DB) as db:
        await db.execute('DELETE FROM tab_presence WHERE user_id = ?', (user_id,))
        await db.commit()
    
    # Insert a tab with recent activity (1 hour ago)
    now = int(time.time())
    recent_time = now - 3600  # 1 hour ago
    
    async with aiosqlite.connect(db_mod.DB) as db:
        await db.execute(
            'INSERT INTO tab_presence (tab_id, jti, user_id, created_at, last_active) VALUES (?, ?, ?, ?, ?)',
            (tab_id, jti, user_id, recent_time, recent_time)
        )
        await db.commit()
        
        # Verify tab exists
        cur = await db.execute('SELECT COUNT(*) FROM tab_presence WHERE tab_id = ?', (tab_id,))
        count = (await cur.fetchone())[0]
        assert count == 1, "Tab should exist before cleanup"
    
    # Run cleanup with default 24-hour threshold
    await cleanup_stale_tabs()
    
    # Verify tab was NOT removed (it's recent)
    async with aiosqlite.connect(db_mod.DB) as db:
        cur = await db.execute('SELECT COUNT(*) FROM tab_presence WHERE tab_id = ?', (tab_id,))
        count = (await cur.fetchone())[0]
        assert count == 1, "Recent tab should be preserved after cleanup"


@pytest.mark.asyncio
async def test_user_goes_offline_when_all_tabs_stale():
    """Verify that a user shows offline after their stale tabs are cleaned up."""
    user_id = 9993
    tab_id = f'tab-cleanup-test-0003-{int(time.time())}'
    jti = f'jti-cleanup-test-0003-{int(time.time())}'
    
    # Clean up first
    async with aiosqlite.connect(db_mod.DB) as db:
        await db.execute('DELETE FROM tab_presence WHERE user_id = ?', (user_id,))
        await db.commit()
    
    # Insert a stale tab (25 hours old)
    now = int(time.time())
    stale_time = now - (86400 + 3600)
    
    async with aiosqlite.connect(db_mod.DB) as db:
        await db.execute(
            'INSERT INTO tab_presence (tab_id, jti, user_id, created_at, last_active) VALUES (?, ?, ?, ?, ?)',
            (tab_id, jti, user_id, stale_time, stale_time)
        )
        await db.commit()
    
    # Before cleanup: user might show as AFK (if inside AFK window) or offline
    # depending on AFK_SECONDS config. Let's check after cleanup.
    
    # Run cleanup via get_presence_status (which calls cleanup internally)
    status = await get_presence_status(user_id)
    
    # After cleanup, all stale tabs are removed, so user should be offline
    assert status == 'offline', f"User should be offline after cleanup, but got {status}"


@pytest.mark.asyncio
async def test_cleanup_called_on_get_presence_status():
    """Verify that get_presence_status calls cleanup automatically."""
    user_id = 9994
    tab_id = f'tab-auto-cleanup-0004-{int(time.time())}'
    jti = f'jti-auto-cleanup-0004-{int(time.time())}'
    
    # Clean up first
    async with aiosqlite.connect(db_mod.DB) as db:
        await db.execute('DELETE FROM tab_presence WHERE user_id = ?', (user_id,))
        await db.commit()
    
    # Insert a stale tab (25 hours old)
    now = int(time.time())
    stale_time = now - (86400 + 3600)
    
    async with aiosqlite.connect(db_mod.DB) as db:
        await db.execute(
            'INSERT INTO tab_presence (tab_id, jti, user_id, created_at, last_active) VALUES (?, ?, ?, ?, ?)',
            (tab_id, jti, user_id, stale_time, stale_time)
        )
        await db.commit()
    
    # Call get_presence_status, which should trigger cleanup
    status = await get_presence_status(user_id)
    
    # Verify tab was removed by cleanup
    async with aiosqlite.connect(db_mod.DB) as db:
        cur = await db.execute('SELECT COUNT(*) FROM tab_presence WHERE tab_id = ?', (tab_id,))
        count = (await cur.fetchone())[0]
        assert count == 0, "Stale tab should be removed by cleanup called from get_presence_status"
    
    # Verify user is offline
    assert status == 'offline', f"User should be offline, but got {status}"


@pytest.mark.asyncio
async def test_cleanup_with_custom_threshold():
    """Verify that cleanup_stale_tabs respects custom max_age_seconds."""
    user_id = 9995
    tab_id = f'tab-custom-threshold-0005-{int(time.time())}'
    jti = f'jti-custom-threshold-0005-{int(time.time())}'
    
    # Clean up first
    async with aiosqlite.connect(db_mod.DB) as db:
        await db.execute('DELETE FROM tab_presence WHERE user_id = ?', (user_id,))
        await db.commit()
    
    # Insert a tab that's 2 hours old
    now = int(time.time())
    old_time = now - 7200  # 2 hours ago
    
    async with aiosqlite.connect(db_mod.DB) as db:
        await db.execute(
            'INSERT INTO tab_presence (tab_id, jti, user_id, created_at, last_active) VALUES (?, ?, ?, ?, ?)',
            (tab_id, jti, user_id, old_time, old_time)
        )
        await db.commit()
    
    # Clean up with 1-hour threshold (this tab should be removed)
    await cleanup_stale_tabs(max_age_seconds=3600)
    
    # Verify tab was removed
    async with aiosqlite.connect(db_mod.DB) as db:
        cur = await db.execute('SELECT COUNT(*) FROM tab_presence WHERE tab_id = ?', (tab_id,))
        count = (await cur.fetchone())[0]
        assert count == 0, "Tab older than custom threshold should be removed"
