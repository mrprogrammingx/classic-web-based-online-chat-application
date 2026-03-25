from fastapi import APIRouter, Depends, HTTPException, Request
import aiosqlite
import time
from utils import require_auth
from db import DB

router = APIRouter()


async def require_admin(user=Depends(require_auth)):
    # check user is admin
    async with aiosqlite.connect(DB) as db:
        cur = await db.execute('SELECT is_admin FROM users WHERE id = ?', (user['id'],))
        row = await cur.fetchone()
        if not row or not row[0]:
            raise HTTPException(status_code=403, detail='admin required')
    return user


@router.get('/admin/users')
async def list_users(request: Request, user=Depends(require_admin)):
    # Support optional server-side filtering, search and pagination via query params
    qs = request.query_params
    flt = qs.get('filter', 'all')
    q = qs.get('q')
    try:
        page = int(qs.get('page', '1'))
        if page < 1: page = 1
    except Exception:
        page = 1
    try:
        per_page = int(qs.get('per_page', '50'))
        if per_page < 1: per_page = 50
    except Exception:
        per_page = 50

    where = []
    params = []

    if flt == 'admins':
        where.append('is_admin = 1')
    elif flt == 'banned':
        where.append('id IN (SELECT banned_id FROM bans)')
    elif flt == 'unbanned':
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
        # total count for the filtered query
        count_q = f"SELECT COUNT(*) FROM users {where_clause}"
        cur = await db.execute(count_q, tuple(params))
        total_row = await cur.fetchone()
        total = total_row[0] if total_row else 0

    # preserve descending order (newest first) for tests and admin UX
    async with aiosqlite.connect(DB) as db:
        qstmt = f"SELECT id, email, username, created_at, is_admin FROM users {where_clause} ORDER BY id DESC LIMIT ? OFFSET ?"
        cur = await db.execute(qstmt, tuple(params) + (per_page, offset))
        rows = await cur.fetchall()
        users = [{'id': r[0], 'email': r[1], 'username': r[2], 'created_at': r[3], 'is_admin': bool(r[4])} for r in rows]
        # also include list of currently banned user ids so front-end doesn't need an extra request
        cur = await db.execute('SELECT DISTINCT banned_id FROM bans')
        banned_rows = await cur.fetchall()
        banned_ids = [r[0] for r in banned_rows]
    return {'users': users, 'total': total, 'page': page, 'per_page': per_page, 'banned_ids': banned_ids}


@router.get('/admin/users/counts')
async def admin_user_counts(user=Depends(require_admin)):
    # return quick counts for filter buttons
    async with aiosqlite.connect(DB) as db:
        cur = await db.execute('SELECT COUNT(*) FROM users')
        total = (await cur.fetchone())[0]
        cur = await db.execute('SELECT COUNT(*) FROM users WHERE is_admin = 1')
        admins = (await cur.fetchone())[0]
        cur = await db.execute('SELECT COUNT(DISTINCT banned_id) FROM bans')
        banned = (await cur.fetchone())[0]
        return {'total': total, 'admins': admins, 'banned': banned}


@router.post('/admin/users/delete')
async def delete_user(request: Request, user=Depends(require_admin)):
    body = await request.json()
    uid = body.get('id')
    if not uid:
        raise HTTPException(status_code=400, detail='id required')
    # When removing a user, also remove or clean up related records that
    # aren't guaranteed to cascade (SQLite foreign keys may be disabled).
    async with aiosqlite.connect(DB) as db:
        # remove global bans where user is banner or banned
        await db.execute('DELETE FROM bans WHERE banner_id = ? OR banned_id = ?', (uid, uid))
        # remove room-level bans, memberships, and room admin entries
        await db.execute('DELETE FROM room_bans WHERE banned_id = ?', (uid,))
        await db.execute('DELETE FROM memberships WHERE user_id = ?', (uid,))
        await db.execute('DELETE FROM room_admins WHERE user_id = ?', (uid,))
        # remove session/tab presence
        await db.execute('DELETE FROM tab_presence WHERE user_id = ?', (uid,))
        await db.execute('DELETE FROM sessions WHERE user_id = ?', (uid,))
        # remove friend relations and requests
        await db.execute('DELETE FROM friends WHERE user_id = ? OR friend_id = ?', (uid, uid))
        await db.execute('DELETE FROM friend_requests WHERE from_id = ? OR to_id = ?', (uid, uid))
        # remove dialog reads / dialog metadata
        await db.execute('DELETE FROM dialog_reads WHERE user_id = ? OR other_id = ?', (uid, uid))
        # remove private message files and private messages (both directions)
        await db.execute('DELETE FROM private_message_files WHERE from_id = ? OR to_id = ?', (uid, uid))
        await db.execute('DELETE FROM private_messages WHERE from_id = ? OR to_id = ?', (uid, uid))
        # remove room message files that belong to messages authored by the user (if any)
        await db.execute('DELETE FROM message_files WHERE message_id IN (SELECT id FROM messages WHERE user_id = ?)', (uid,))
        # remove room messages authored by the user
        await db.execute('DELETE FROM messages WHERE user_id = ?', (uid,))
        # finally, remove the user row itself; rooms owned by the user will keep owner_id NULL
        await db.execute('DELETE FROM users WHERE id = ?', (uid,))
        await db.commit()
    return {'ok': True}


@router.post('/admin/users/promote')
async def promote_user(request: Request, user=Depends(require_admin)):
    """Promote a user to admin. Body: { id: <user_id> }"""
    body = await request.json()
    uid = body.get('id')
    if not uid:
        raise HTTPException(status_code=400, detail='id required')
    async with aiosqlite.connect(DB) as db:
        await db.execute('UPDATE users SET is_admin = 1 WHERE id = ?', (uid,))
        await db.commit()
    return {'ok': True}


@router.get('/admin/rooms')
async def list_rooms(user=Depends(require_admin)):
    # return rooms with owner username and member counts to help admin UI
    async with aiosqlite.connect(DB) as db:
        cur = await db.execute('''
            SELECT r.id, r.owner_id, r.name, r.created_at, u.username,
                   (SELECT COUNT(*) FROM memberships m WHERE m.room_id = r.id) as member_count
            FROM rooms r LEFT JOIN users u ON r.owner_id = u.id
            ORDER BY r.id ASC
        ''')
        rows = await cur.fetchall()
        return {'rooms': [
            {'id': r[0], 'owner_id': r[1], 'name': r[2], 'created_at': r[3], 'owner_username': r[4], 'member_count': r[5]}
            for r in rows
        ]}


@router.get('/admin/banned')
async def list_banned(user=Depends(require_admin)):
    async with aiosqlite.connect(DB) as db:
        cur = await db.execute('SELECT b.id, b.banned_id, u.username, u.email, b.banner_id, b.created_at FROM bans b LEFT JOIN users u ON b.banned_id = u.id')
        rows = await cur.fetchall()
        return {'banned': [{'id': r[0], 'banned_id': r[1], 'username': r[2], 'email': r[3], 'banner_id': r[4], 'created_at': r[5]} for r in rows]}


@router.post('/admin/ban_user')
async def ban_user(request: Request, user=Depends(require_admin)):
    body = await request.json()
    uid = body.get('user_id') or body.get('id')
    if not uid:
        raise HTTPException(status_code=400, detail='user_id required')
    async with aiosqlite.connect(DB) as db:
        try:
            await db.execute('INSERT INTO bans (banner_id, banned_id, created_at) VALUES (?, ?, ?)', (user['id'], uid, int(time.time())))
            await db.commit()
        except aiosqlite.IntegrityError:
            # already banned
            pass
    return {'ok': True}


@router.post('/admin/unban_user')
async def unban_user(request: Request, user=Depends(require_admin)):
    body = await request.json()
    uid = body.get('user_id') or body.get('id')
    if not uid:
        raise HTTPException(status_code=400, detail='user_id required')
    async with aiosqlite.connect(DB) as db:
        await db.execute('DELETE FROM bans WHERE banned_id = ?', (uid,))
        await db.commit()
    return {'ok': True}


@router.post('/admin/make_admin')
async def make_admin(request: Request, user=Depends(require_admin)):
    body = await request.json()
    uid = body.get('user_id') or body.get('id')
    if not uid:
        raise HTTPException(status_code=400, detail='user id required')
    async with aiosqlite.connect(DB) as db:
        await db.execute('UPDATE users SET is_admin = 1 WHERE id = ?', (uid,))
        await db.commit()
    return {'ok': True}


@router.post('/admin/revoke_admin')
async def revoke_admin(request: Request, user=Depends(require_admin)):
    body = await request.json()
    uid = body.get('user_id') or body.get('id')
    if not uid:
        raise HTTPException(status_code=400, detail='user id required')
    async with aiosqlite.connect(DB) as db:
        await db.execute('UPDATE users SET is_admin = 0 WHERE id = ?', (uid,))
        await db.commit()
    return {'ok': True}


@router.post('/admin/delete_room')
async def admin_delete_room(request: Request, user=Depends(require_admin)):
    body = await request.json()
    rid = body.get('room_id') or body.get('id')
    if not rid:
        raise HTTPException(status_code=400, detail='room_id required')
    # Clean up related objects that may not cascade if foreign keys are disabled
    async with aiosqlite.connect(DB) as db:
        # gather counts for audit
        cur = await db.execute('SELECT COUNT(*) FROM messages WHERE room_id = ?', (rid,))
        messages_before = (await cur.fetchone())[0]
        cur = await db.execute('SELECT COUNT(*) FROM message_files WHERE message_id IN (SELECT id FROM messages WHERE room_id = ?)', (rid,))
        message_files_before = (await cur.fetchone())[0]
        cur = await db.execute('SELECT COUNT(*) FROM room_files WHERE room_id = ?', (rid,))
        room_files_before = (await cur.fetchone())[0]
        cur = await db.execute('SELECT COUNT(*) FROM memberships WHERE room_id = ?', (rid,))
        memberships_before = (await cur.fetchone())[0]
        cur = await db.execute('SELECT COUNT(*) FROM room_admins WHERE room_id = ?', (rid,))
        room_admins_before = (await cur.fetchone())[0]
        cur = await db.execute('SELECT COUNT(*) FROM room_bans WHERE room_id = ?', (rid,))
        room_bans_before = (await cur.fetchone())[0]
        cur = await db.execute('SELECT COUNT(*) FROM invitations WHERE room_id = ?', (rid,))
        invitations_before = (await cur.fetchone())[0]

        # perform deletions
        await db.execute('DELETE FROM message_files WHERE message_id IN (SELECT id FROM messages WHERE room_id = ?)', (rid,))
        await db.execute('DELETE FROM messages WHERE room_id = ?', (rid,))
        await db.execute('DELETE FROM room_files WHERE room_id = ?', (rid,))
        await db.execute('DELETE FROM memberships WHERE room_id = ?', (rid,))
        await db.execute('DELETE FROM room_admins WHERE room_id = ?', (rid,))
        await db.execute('DELETE FROM room_bans WHERE room_id = ?', (rid,))
        await db.execute('DELETE FROM invitations WHERE room_id = ?', (rid,))
        await db.execute('DELETE FROM rooms WHERE id = ?', (rid,))
        await db.commit()

    return {
        'ok': True,
        'deleted': {
            'messages': messages_before,
            'message_files': message_files_before,
            'room_files': room_files_before,
            'memberships': memberships_before,
            'room_admins': room_admins_before,
            'room_bans': room_bans_before,
            'invitations': invitations_before,
            'room': 1
        }
    }


@router.post('/admin/delete_message')
async def admin_delete_message(request: Request, user=Depends(require_admin)):
    body = await request.json()
    mid = body.get('message_id') or body.get('id')
    if not mid:
        raise HTTPException(status_code=400, detail='message_id required')
    async with aiosqlite.connect(DB) as db:
        # counts for audit
        cur = await db.execute('SELECT COUNT(*) FROM message_files WHERE message_id = ?', (mid,))
        message_files_before = (await cur.fetchone())[0]
        cur = await db.execute('SELECT room_file_id FROM message_files WHERE message_id = ?', (mid,))
        rf_rows = await cur.fetchall()
        room_file_ids = [r[0] for r in rf_rows]
        # delete message_files rows
        await db.execute('DELETE FROM message_files WHERE message_id = ?', (mid,))
        # delete room message
        cur = await db.execute('SELECT COUNT(*) FROM messages WHERE id = ?', (mid,))
        messages_before = (await cur.fetchone())[0]
        await db.execute('DELETE FROM messages WHERE id = ?', (mid,))
        # delete private message
        cur = await db.execute('SELECT COUNT(*) FROM private_messages WHERE id = ?', (mid,))
        private_before = (await cur.fetchone())[0]
        await db.execute('DELETE FROM private_messages WHERE id = ?', (mid,))
        # delete any room_files referenced by this message
        room_files_deleted = 0
        if room_file_ids:
            q = 'DELETE FROM room_files WHERE id IN ({})'.format(','.join(['?']*len(room_file_ids)))
            await db.execute(q, tuple(room_file_ids))
            room_files_deleted = len(room_file_ids)
        await db.commit()

    return {
        'ok': True,
        'deleted': {
            'messages': messages_before,
            'private_messages': private_before,
            'message_files': message_files_before,
            'room_files': room_files_deleted
        }
    }


@router.get('/admin/messages')
async def admin_list_messages(request: Request, user=Depends(require_admin)):
    """List messages for admin moderation. Supports optional search `q`, `page`, `per_page`, and `room_id`."""
    qs = request.query_params
    q = qs.get('q')
    try:
        page = int(qs.get('page', '1'))
        if page < 1: page = 1
    except Exception:
        page = 1
    try:
        per_page = int(qs.get('per_page', '50'))
        if per_page < 1: per_page = 50
    except Exception:
        per_page = 50
    room_id = qs.get('room_id')

    where = []
    params = []
    if room_id:
        where.append('m.room_id = ?')
        params.append(int(room_id))
    if q:
        if q.isdigit():
            where.append('m.id = ?')
            params.append(int(q))
        else:
            where.append('m.text LIKE ?')
            params.append(f"%{q}%")
    where_clause = ('WHERE ' + ' AND '.join(where)) if where else ''
    offset = (page - 1) * per_page

    async with aiosqlite.connect(DB) as db:
        count_q = f"SELECT COUNT(*) FROM messages m {where_clause}"
        cur = await db.execute(count_q, tuple(params))
        total = (await cur.fetchone())[0]

        sql = f"""
        SELECT m.id, m.room_id, r.name, m.user_id, u.username, m.text, m.created_at
        FROM messages m
        LEFT JOIN users u ON m.user_id = u.id
        LEFT JOIN rooms r ON m.room_id = r.id
        {where_clause}
        ORDER BY m.created_at DESC
        LIMIT ? OFFSET ?
        """
        cur = await db.execute(sql, tuple(params) + (per_page, offset))
        rows = await cur.fetchall()
        msgs = [
            {'id': r[0], 'room_id': r[1], 'room_name': r[2], 'user_id': r[3], 'username': r[4], 'text': r[5], 'created_at': r[6]}
            for r in rows
        ]
    return {'messages': msgs, 'total': total, 'page': page, 'per_page': per_page}


@router.post('/admin/remove_member')
async def admin_remove_member(request: Request, user=Depends(require_admin)):
    body = await request.json()
    rid = body.get('room_id')
    uid = body.get('user_id')
    if not rid or not uid:
        raise HTTPException(status_code=400, detail='room_id and user_id required')
    async with aiosqlite.connect(DB) as db:
        await db.execute('DELETE FROM memberships WHERE room_id = ? AND user_id = ?', (rid, uid))
        await db.commit()
    return {'ok': True}
