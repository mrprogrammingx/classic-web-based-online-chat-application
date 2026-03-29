import aiosqlite
import time
from typing import Optional, List, Dict
import db as db_mod


async def list_friends_for_user(user_id: int) -> List[Dict]:
    async with aiosqlite.connect(db_mod.schema._db_path()) as conn:
        cur = await conn.execute(
            'SELECT u.id, u.email, u.username, u.is_admin FROM users u JOIN friends f ON f.friend_id = u.id WHERE f.user_id = ?',
            (user_id,)
        )
        rows = await cur.fetchall()
        return [{'id': r[0], 'email': r[1], 'username': r[2], 'is_admin': bool(r[3])} for r in rows]


async def add_friend_relation(user_id: int, fid: int) -> None:
    async with aiosqlite.connect(db_mod.schema._db_path()) as conn:
        try:
            await conn.execute('INSERT INTO friends (user_id, friend_id, created_at) VALUES (?, ?, ?)', (user_id, fid, int(time.time())))
            await conn.commit()
        except aiosqlite.IntegrityError:
            raise


async def create_friend_request(from_id: int, username: Optional[str], fid: Optional[int], message: Optional[str]) -> int:
    async with aiosqlite.connect(db_mod.schema._db_path()) as conn:
        if username and not fid:
            cur = await conn.execute('SELECT id FROM users WHERE username = ?', (username,))
            row = await cur.fetchone()
            if not row:
                raise LookupError('user not found')
            fid = row[0]
        if not fid:
            raise ValueError('username or friend_id required')
        if fid == from_id:
            raise ValueError("can't request yourself")
        # check for existing ban (either direction)
        cur = await conn.execute(
            'SELECT 1 FROM bans WHERE (banner_id = ? AND banned_id = ?) OR (banner_id = ? AND banned_id = ?)',
            (from_id, fid, fid, from_id),
        )
        if await cur.fetchone():
            raise PermissionError('ban exists between users')
        # check for existing pending friend request (duplicate)
        cur = await conn.execute('SELECT 1 FROM friend_requests WHERE from_id = ? AND to_id = ? AND status = ?', (from_id, fid, 'pending'))
        if await cur.fetchone():
            raise ValueError('friend request already pending')
        # check if already friends
        cur = await conn.execute('SELECT 1 FROM friends WHERE (user_id = ? AND friend_id = ?) OR (user_id = ? AND friend_id = ?)', (from_id, fid, from_id, fid))
        if await cur.fetchone():
            raise ValueError('already friends')
        try:
            await conn.execute('INSERT INTO friend_requests (from_id, to_id, message, created_at) VALUES (?, ?, ?, ?)', (from_id, fid, message, int(time.time())))
            await conn.commit()
            return 1
        except aiosqlite.IntegrityError:
            raise


async def list_incoming_requests_for_user(user_id: int):
    async with aiosqlite.connect(db_mod.schema._db_path()) as conn:
        cur = await conn.execute(
            'SELECT fr.id, fr.from_id, u.username, u.email, fr.message, fr.status, fr.created_at '
            'FROM friend_requests fr JOIN users u ON u.id = fr.from_id '
            'WHERE fr.to_id = ? AND fr.status = ?',
            (user_id, 'pending'),
        )
        rows = await cur.fetchall()
        return [{'id': r[0], 'from_id': r[1], 'username': r[2], 'email': r[3], 'message': r[4], 'status': r[5], 'created_at': r[6]} for r in rows]


async def respond_to_request(user_id: int, rid: int, action: str) -> None:
    async with aiosqlite.connect(db_mod.schema._db_path()) as conn:
        cur = await conn.execute('SELECT from_id, to_id FROM friend_requests WHERE id = ? AND to_id = ? AND status = ?', (rid, user_id, 'pending'))
        row = await cur.fetchone()
        if not row:
            raise LookupError('request not found')
        from_id = row[0]
        if action == 'reject':
            await conn.execute('UPDATE friend_requests SET status = ? WHERE id = ?', ('rejected', rid))
            await conn.commit()
            return
        # accept: create mutual friendship entries (both directions)
        await conn.execute('UPDATE friend_requests SET status = ? WHERE id = ?', ('accepted', rid))
        try:
            await conn.execute('INSERT INTO friends (user_id, friend_id, created_at) VALUES (?, ?, ?)', (user_id, from_id, int(time.time())))
        except aiosqlite.IntegrityError:
            pass
        try:
            await conn.execute('INSERT INTO friends (user_id, friend_id, created_at) VALUES (?, ?, ?)', (from_id, user_id, int(time.time())))
        except aiosqlite.IntegrityError:
            pass
        await conn.commit()


async def ban_user_action(user_id: int, banned_id: int) -> None:
    async with aiosqlite.connect(db_mod.schema._db_path()) as conn:
        try:
            await conn.execute('INSERT INTO bans (banner_id, banned_id, created_at) VALUES (?, ?, ?)', (user_id, banned_id, int(time.time())))
            # remove friendships both directions
            await conn.execute('DELETE FROM friends WHERE (user_id = ? AND friend_id = ?) OR (user_id = ? AND friend_id = ?)', (user_id, banned_id, banned_id, user_id))
            # remove pending friend requests both directions
            await conn.execute('DELETE FROM friend_requests WHERE (from_id = ? AND to_id = ?) OR (from_id = ? AND to_id = ?)', (user_id, banned_id, banned_id, user_id))
            await conn.commit()
        except aiosqlite.IntegrityError:
            # already banned
            pass


async def check_ban_for_users(user_id: int, other_id: int) -> bool:
    async with aiosqlite.connect(db_mod.schema._db_path()) as conn:
        cur = await conn.execute('SELECT 1 FROM bans WHERE (banner_id = ? AND banned_id = ?) OR (banner_id = ? AND banned_id = ?)', (user_id, other_id, other_id, user_id))
        row = await cur.fetchone()
        return bool(row)


async def list_bans_for_user(user_id: int):
    async with aiosqlite.connect(db_mod.schema._db_path()) as conn:
        cur = await conn.execute('SELECT b.banned_id, u.username, u.email, b.created_at FROM bans b LEFT JOIN users u ON u.id = b.banned_id WHERE b.banner_id = ?', (user_id,))
        rows = await cur.fetchall()
        return [{'banned_id': r[0], 'username': r[1], 'email': r[2], 'created_at': r[3]} for r in rows]


async def unban_user_action(user_id: int, banned_id: int) -> None:
    async with aiosqlite.connect(db_mod.schema._db_path()) as conn:
        await conn.execute('DELETE FROM bans WHERE banner_id = ? AND banned_id = ?', (user_id, banned_id))
        await conn.commit()


async def remove_friend_action(user_id: int, fid: int) -> None:
    async with aiosqlite.connect(db_mod.schema._db_path()) as conn:
        await conn.execute('DELETE FROM friends WHERE user_id = ? AND friend_id = ?', (user_id, fid))
        await conn.commit()
