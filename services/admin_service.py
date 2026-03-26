import aiosqlite
import time
from typing import List, Dict, Optional, Tuple
from db import DB


async def list_users(filter_clause: Optional[str], q: Optional[str], page: int = 1, per_page: int = 50) -> Tuple[List[Dict], int]:
    where = []
    params = []
    if filter_clause == 'admins':
        where.append('is_admin = 1')
    elif filter_clause == 'banned':
        where.append('id IN (SELECT banned_id FROM bans)')
    elif filter_clause == 'unbanned':
        where.append('id NOT IN (SELECT banned_id FROM bans)')

    if q:
        if q.isdigit():
            where.append('id = ?')
            params.append(int(q))
        else:
            where.append('(username LIKE ? OR email LIKE ?)')
            like = f"%{q}%"
            params.extend([like, like])

    where_clause = ('WHERE ' + ' AND '.join(where)) if where else ''
    offset = (page - 1) * per_page

    async with aiosqlite.connect(DB) as db:
        count_q = f"SELECT COUNT(*) FROM users {where_clause}"
        cur = await db.execute(count_q, tuple(params))
        total_row = await cur.fetchone()
        total = total_row[0] if total_row else 0

        qstmt = f"SELECT id, email, username, created_at, is_admin FROM users {where_clause} ORDER BY id DESC LIMIT ? OFFSET ?"
        cur = await db.execute(qstmt, tuple(params) + (per_page, offset))
        rows = await cur.fetchall()
        users = [{'id': r[0], 'email': r[1], 'username': r[2], 'created_at': r[3], 'is_admin': bool(r[4])} for r in rows]

        cur = await db.execute('SELECT DISTINCT banned_id FROM bans')
        banned_rows = await cur.fetchall()
        banned_ids = [r[0] for r in banned_rows]

    return users, total, banned_ids


async def admin_user_counts() -> Dict[str, int]:
    async with aiosqlite.connect(DB) as db:
        cur = await db.execute('SELECT COUNT(*) FROM users')
        total = (await cur.fetchone())[0]
        cur = await db.execute('SELECT COUNT(*) FROM users WHERE is_admin = 1')
        admins = (await cur.fetchone())[0]
        cur = await db.execute('SELECT COUNT(DISTINCT banned_id) FROM bans')
        banned = (await cur.fetchone())[0]
        return {'total': total, 'admins': admins, 'banned': banned}


async def delete_user_and_cleanup(uid: int) -> None:
    async with aiosqlite.connect(DB) as db:
        # remove related records similar to original admin.delete_user
        await db.execute('DELETE FROM bans WHERE banner_id = ? OR banned_id = ?', (uid, uid))
        await db.execute('DELETE FROM room_bans WHERE banned_id = ?', (uid,))
        await db.execute('DELETE FROM memberships WHERE user_id = ?', (uid,))
        await db.execute('DELETE FROM room_admins WHERE user_id = ?', (uid,))
        await db.execute('DELETE FROM tab_presence WHERE user_id = ?', (uid,))
        await db.execute('DELETE FROM sessions WHERE user_id = ?', (uid,))
        await db.execute('DELETE FROM friends WHERE user_id = ? OR friend_id = ?', (uid, uid))
        await db.execute('DELETE FROM friend_requests WHERE from_id = ? OR to_id = ?', (uid, uid))
        await db.execute('DELETE FROM dialog_reads WHERE user_id = ? OR other_id = ?', (uid, uid))
        await db.execute('DELETE FROM private_message_files WHERE from_id = ? OR to_id = ?', (uid, uid))
        await db.execute('DELETE FROM private_messages WHERE from_id = ? OR to_id = ?', (uid, uid))
        await db.execute('DELETE FROM message_files WHERE message_id IN (SELECT id FROM messages WHERE user_id = ?)', (uid,))
        await db.execute('DELETE FROM messages WHERE user_id = ?', (uid,))
        await db.execute('DELETE FROM users WHERE id = ?', (uid,))
        await db.commit()


async def set_admin(uid: int, is_admin: bool) -> None:
    async with aiosqlite.connect(DB) as db:
        await db.execute('UPDATE users SET is_admin = ? WHERE id = ?', (1 if is_admin else 0, uid))
        await db.commit()


async def ban_user(banner_id: int, banned_id: int) -> None:
    async with aiosqlite.connect(DB) as db:
        try:
            await db.execute('INSERT INTO bans (banner_id, banned_id, created_at) VALUES (?, ?, ?)', (banner_id, banned_id, int(time.time())))
            await db.commit()
        except aiosqlite.IntegrityError:
            pass


async def unban_user(banned_id: int) -> None:
    async with aiosqlite.connect(DB) as db:
        await db.execute('DELETE FROM bans WHERE banned_id = ?', (banned_id,))
        await db.commit()
