from fastapi import APIRouter, Depends, HTTPException, Request
import os
import aiosqlite
import time
from utils import require_auth
from db import DB
from services import admin_service

router = APIRouter()


async def require_admin(user=Depends(require_auth)):
    # In test mode or when no admin exists yet, allow an authenticated user to act
    # as an admin (bootstrap). This makes it easy to run E2E tests that promote
    # the first user to admin without manual seeding. In normal operation, the
    # caller must have is_admin set in the database.
    if os.getenv('TEST_MODE') == '1':
        return user

    async with aiosqlite.connect(DB) as db:
        # if there are no admins yet, allow bootstrap promotion
        cur = await db.execute('SELECT COUNT(*) FROM users WHERE is_admin = 1')
        row = await cur.fetchone()
        total_admins = row[0] if row else 0
        if total_admins == 0:
            return user

        # otherwise enforce admin check
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

    # Delegate DB-heavy work to admin_service
    users, total, banned_ids = await admin_service.list_users(flt if flt != 'all' else None, q, page=page, per_page=per_page)
    return {'users': users, 'total': total, 'page': page, 'per_page': per_page, 'banned_ids': banned_ids}


@router.get('/admin/users/counts')
async def admin_user_counts(user=Depends(require_admin)):
    # return quick counts for filter buttons
    return await admin_service.admin_user_counts()


@router.post('/admin/users/delete')
async def delete_user(request: Request, user=Depends(require_admin)):
    body = await request.json()
    uid = body.get('id')
    if not uid:
        raise HTTPException(status_code=400, detail='id required')
    # When removing a user, also remove or clean up related records that
    # aren't guaranteed to cascade (SQLite foreign keys may be disabled).
    await admin_service.delete_user_and_cleanup(uid)
    return {'ok': True}


@router.post('/admin/users/promote')
async def promote_user(request: Request, user=Depends(require_admin)):
    """Promote a user to admin. Body: { id: <user_id> }"""
    body = await request.json()
    uid = body.get('id')
    if not uid:
        raise HTTPException(status_code=400, detail='id required')
    await admin_service.set_admin(uid, True)
    return {'ok': True}


@router.get('/admin/rooms')
async def list_rooms(request: Request, user=Depends(require_admin)):
    """Return rooms with optional pagination: ?page=&per_page"""
    qs = request.query_params
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

    q = qs.get('q')
    offset = (page - 1) * per_page

    async with aiosqlite.connect(DB) as db:
        # total count (respecting query if present)
        if q:
            if q.isdigit():
                cur = await db.execute('SELECT COUNT(*) FROM rooms WHERE id = ?', (int(q),))
            else:
                cur = await db.execute('SELECT COUNT(*) FROM rooms WHERE name LIKE ?', (f'%{q}%',))
        else:
            cur = await db.execute('SELECT COUNT(*) FROM rooms')
        total = (await cur.fetchone())[0]

        if q:
            if q.isdigit():
                sql = '''
                    SELECT r.id, r.owner_id, r.name, r.created_at, u.username,
                           (SELECT COUNT(*) FROM memberships m WHERE m.room_id = r.id) as member_count
                    FROM rooms r LEFT JOIN users u ON r.owner_id = u.id
                    WHERE r.id = ?
                    ORDER BY r.id ASC
                    LIMIT ? OFFSET ?
                '''
                cur = await db.execute(sql, (int(q), per_page, offset))
            else:
                sql = '''
                    SELECT r.id, r.owner_id, r.name, r.created_at, u.username,
                           (SELECT COUNT(*) FROM memberships m WHERE m.room_id = r.id) as member_count
                    FROM rooms r LEFT JOIN users u ON r.owner_id = u.id
                    WHERE r.name LIKE ?
                    ORDER BY r.id ASC
                    LIMIT ? OFFSET ?
                '''
                cur = await db.execute(sql, (f'%{q}%', per_page, offset))
        else:
            sql = '''
                SELECT r.id, r.owner_id, r.name, r.created_at, u.username,
                       (SELECT COUNT(*) FROM memberships m WHERE m.room_id = r.id) as member_count
                FROM rooms r LEFT JOIN users u ON r.owner_id = u.id
                ORDER BY r.id ASC
                LIMIT ? OFFSET ?
            '''
            cur = await db.execute(sql, (per_page, offset))

        rows = await cur.fetchall()
        rooms = [
            {'id': r[0], 'owner_id': r[1], 'name': r[2], 'created_at': r[3], 'owner_username': r[4], 'member_count': r[5]}
            for r in rows
        ]

    return {'rooms': rooms, 'total': total, 'page': page, 'per_page': per_page}


@router.get('/admin/banned')
async def list_banned(request: Request, user=Depends(require_admin)):
    """List banned users with optional pagination: ?page=&per_page="""
    qs = request.query_params
    try:
        page = int(qs.get('page', '1'))
        if page < 1:
            page = 1
    except Exception:
        page = 1
    try:
        per_page = int(qs.get('per_page', '50'))
        if per_page < 1:
            per_page = 50
    except Exception:
        per_page = 50

    offset = (page - 1) * per_page
    # read optional search query
    q = qs.get('q')

    async with aiosqlite.connect(DB) as db:
        # total count for pager (respect q when present)
        if q:
            if q.isdigit():
                cur = await db.execute('SELECT COUNT(*) FROM bans WHERE banned_id = ?', (int(q),))
            else:
                cur = await db.execute(
                    'SELECT COUNT(*) FROM bans b LEFT JOIN users u ON b.banned_id = u.id WHERE u.username LIKE ? OR u.email LIKE ?',
                    (f'%{q}%', f'%{q}%')
                )
        else:
            cur = await db.execute('SELECT COUNT(*) FROM bans')
        total = (await cur.fetchone())[0]

        # apply optional search q to bans
        if q:
            if q.isdigit():
                cur = await db.execute(
                    'SELECT b.id, b.banned_id, u.username, u.email, b.banner_id, b.created_at '
                    'FROM bans b LEFT JOIN users u ON b.banned_id = u.id '
                    'WHERE b.banned_id = ? '
                    'ORDER BY b.id DESC LIMIT ? OFFSET ?', (int(q), per_page, offset)
                )
            else:
                cur = await db.execute(
                    'SELECT b.id, b.banned_id, u.username, u.email, b.banner_id, b.created_at '
                    'FROM bans b LEFT JOIN users u ON b.banned_id = u.id '
                    'WHERE u.username LIKE ? OR u.email LIKE ? '
                    'ORDER BY b.id DESC LIMIT ? OFFSET ?', (f'%{q}%', f'%{q}%', per_page, offset)
                )
        else:
            cur = await db.execute(
                'SELECT b.id, b.banned_id, u.username, u.email, b.banner_id, b.created_at '
                'FROM bans b LEFT JOIN users u ON b.banned_id = u.id '
                'ORDER BY b.id DESC LIMIT ? OFFSET ?', (per_page, offset)
            )
        rows = await cur.fetchall()
        banned = [
            {'id': r[0], 'banned_id': r[1], 'username': r[2], 'email': r[3], 'banner_id': r[4], 'created_at': r[5]}
            for r in rows
        ]

    return {'banned': banned, 'total': total, 'page': page, 'per_page': per_page}


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
