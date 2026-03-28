import aiosqlite
import time
from typing import List, Dict, Optional, Tuple
import db as db_pkg


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

    async with aiosqlite.connect(db_pkg.DB) as conn:
        count_q = f"SELECT COUNT(*) FROM users {where_clause}"
        cur = await conn.execute(count_q, tuple(params))
        total_row = await cur.fetchone()
        total = total_row[0] if total_row else 0

        qstmt = f"SELECT id, email, username, created_at, is_admin FROM users {where_clause} ORDER BY id DESC LIMIT ? OFFSET ?"
        cur = await conn.execute(qstmt, tuple(params) + (per_page, offset))
        rows = await cur.fetchall()
        users = [{'id': r[0], 'email': r[1], 'username': r[2], 'created_at': r[3], 'is_admin': bool(r[4])} for r in rows]

        cur = await conn.execute('SELECT DISTINCT banned_id FROM bans')
        banned_rows = await cur.fetchall()
        banned_ids = [r[0] for r in banned_rows]

    return users, total, banned_ids


async def admin_user_counts() -> Dict[str, int]:
    async with aiosqlite.connect(db_pkg.DB) as conn:
        cur = await conn.execute('SELECT COUNT(*) FROM users')
        total = (await cur.fetchone())[0]
        cur = await conn.execute('SELECT COUNT(*) FROM users WHERE is_admin = 1')
        admins = (await cur.fetchone())[0]
        cur = await conn.execute('SELECT COUNT(DISTINCT banned_id) FROM bans')
        banned = (await cur.fetchone())[0]
        return {'total': total, 'admins': admins, 'banned': banned}


async def delete_user_and_cleanup(uid: int) -> None:
    async with aiosqlite.connect(db_pkg.DB) as conn:
        # remove related records similar to original admin.delete_user
        await conn.execute('DELETE FROM bans WHERE banner_id = ? OR banned_id = ?', (uid, uid))
        await conn.execute('DELETE FROM room_bans WHERE banned_id = ?', (uid,))
        await conn.execute('DELETE FROM memberships WHERE user_id = ?', (uid,))
        await conn.execute('DELETE FROM room_admins WHERE user_id = ?', (uid,))
        await conn.execute('DELETE FROM tab_presence WHERE user_id = ?', (uid,))
        await conn.execute('DELETE FROM sessions WHERE user_id = ?', (uid,))
        await conn.execute('DELETE FROM friends WHERE user_id = ? OR friend_id = ?', (uid, uid))
        await conn.execute('DELETE FROM friend_requests WHERE from_id = ? OR to_id = ?', (uid, uid))
        await conn.execute('DELETE FROM dialog_reads WHERE user_id = ? OR other_id = ?', (uid, uid))
        await conn.execute('DELETE FROM private_message_files WHERE from_id = ? OR to_id = ?', (uid, uid))
        await conn.execute('DELETE FROM private_messages WHERE from_id = ? OR to_id = ?', (uid, uid))
        await conn.execute('DELETE FROM message_files WHERE message_id IN (SELECT id FROM messages WHERE user_id = ?)', (uid,))
        await conn.execute('DELETE FROM messages WHERE user_id = ?', (uid,))
        await conn.execute('DELETE FROM users WHERE id = ?', (uid,))
        await conn.commit()


async def set_admin(uid: int, is_admin: bool) -> None:
    async with aiosqlite.connect(db_pkg.DB) as conn:
        await conn.execute('UPDATE users SET is_admin = ? WHERE id = ?', (1 if is_admin else 0, uid))
        await conn.commit()


async def ban_user(banner_id: int, banned_id: int) -> None:
    async with aiosqlite.connect(db_pkg.DB) as conn:
        try:
            await conn.execute('INSERT INTO bans (banner_id, banned_id, created_at) VALUES (?, ?, ?)', (banner_id, banned_id, int(time.time())))
            await conn.commit()
        except aiosqlite.IntegrityError:
            pass


async def unban_user(banned_id: int) -> None:
    async with aiosqlite.connect(db_pkg.DB) as conn:
        await conn.execute('DELETE FROM bans WHERE banned_id = ?', (banned_id,))
        await conn.commit()


async def delete_room_and_cleanup(rid: int) -> Dict[str, int]:
    """Delete a room and related objects. Returns counts of deleted rows for audit."""
    async with aiosqlite.connect(db_pkg.DB) as conn:
        cur = await conn.execute('SELECT COUNT(*) FROM messages WHERE room_id = ?', (rid,))
        messages_before = (await cur.fetchone())[0]
        cur = await conn.execute('SELECT COUNT(*) FROM message_files WHERE message_id IN (SELECT id FROM messages WHERE room_id = ?)', (rid,))
        message_files_before = (await cur.fetchone())[0]
        cur = await conn.execute('SELECT COUNT(*) FROM room_files WHERE room_id = ?', (rid,))
        room_files_before = (await cur.fetchone())[0]
        cur = await conn.execute('SELECT COUNT(*) FROM memberships WHERE room_id = ?', (rid,))
        memberships_before = (await cur.fetchone())[0]
        cur = await conn.execute('SELECT COUNT(*) FROM room_admins WHERE room_id = ?', (rid,))
        room_admins_before = (await cur.fetchone())[0]
        cur = await conn.execute('SELECT COUNT(*) FROM room_bans WHERE room_id = ?', (rid,))
        room_bans_before = (await cur.fetchone())[0]
        cur = await conn.execute('SELECT COUNT(*) FROM invitations WHERE room_id = ?', (rid,))
        invitations_before = (await cur.fetchone())[0]

        # perform deletions (DB-only)
        await conn.execute('DELETE FROM message_files WHERE message_id IN (SELECT id FROM messages WHERE room_id = ?)', (rid,))
        await conn.execute('DELETE FROM messages WHERE room_id = ?', (rid,))
        await conn.execute('DELETE FROM room_files WHERE room_id = ?', (rid,))
        await conn.execute('DELETE FROM memberships WHERE room_id = ?', (rid,))
        await conn.execute('DELETE FROM room_admins WHERE room_id = ?', (rid,))
        await conn.execute('DELETE FROM room_bans WHERE room_id = ?', (rid,))
        await conn.execute('DELETE FROM invitations WHERE room_id = ?', (rid,))
        await conn.execute('DELETE FROM rooms WHERE id = ?', (rid,))
        await conn.commit()

    return {
        'messages': messages_before,
        'message_files': message_files_before,
        'room_files': room_files_before,
        'memberships': memberships_before,
        'room_admins': room_admins_before,
        'room_bans': room_bans_before,
        'invitations': invitations_before,
        'room': 1,
    }


async def delete_message_and_cleanup(mid: int) -> Dict[str, int]:
    """Delete a message and related files; returns counts for audit."""
    async with aiosqlite.connect(db_pkg.DB) as conn:
        # determine whether this id refers to a room message, a private message, or both
        cur = await conn.execute('SELECT COUNT(*) FROM messages WHERE id = ?', (mid,))
        messages_before = (await cur.fetchone())[0]
        cur = await conn.execute('SELECT COUNT(*) FROM private_messages WHERE id = ?', (mid,))
        private_before = (await cur.fetchone())[0]

        # counts for audit
        message_files_before = 0
        private_message_files_before = 0
        room_file_ids = []

        if messages_before:
            cur = await conn.execute('SELECT COUNT(*) FROM message_files WHERE message_id = ?', (mid,))
            message_files_before = (await cur.fetchone())[0]
            cur = await conn.execute('SELECT room_file_id FROM message_files WHERE message_id = ?', (mid,))
            rf_rows = await cur.fetchall()
            room_file_ids = [r[0] for r in rf_rows]

        if private_before:
            cur = await conn.execute('SELECT COUNT(*) FROM private_message_files WHERE message_id = ?', (mid,))
            private_message_files_before = (await cur.fetchone())[0]

        # delete rows for room message if present
        room_files_deleted = 0
        if messages_before:
            await conn.execute('DELETE FROM message_files WHERE message_id = ?', (mid,))
            await conn.execute('DELETE FROM messages WHERE id = ?', (mid,))
            if room_file_ids:
                q = 'DELETE FROM room_files WHERE id IN ({})'.format(','.join(['?'] * len(room_file_ids)))
                await conn.execute(q, tuple(room_file_ids))
                room_files_deleted = len(room_file_ids)

        # delete rows for private messages if present
        if private_before:
            await conn.execute('DELETE FROM private_message_files WHERE message_id = ?', (mid,))
            await conn.execute('DELETE FROM private_messages WHERE id = ?', (mid,))

        await conn.commit()

    return {
        'messages': messages_before,
        'private_messages': private_before,
        'message_files': message_files_before,
        'private_message_files': private_message_files_before,
        'room_files': room_files_deleted,
    }
