from fastapi import APIRouter, Depends, HTTPException, Request
import os
import aiosqlite
import time
from routers.utils import require_auth
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


def _parse_pagination(request: Request, default_per_page: int = 50):
    qs = request.query_params
    try:
        page = int(qs.get('page', '1'))
        if page < 1:
            page = 1
    except Exception:
        page = 1
    try:
        per_page = int(qs.get('per_page', str(default_per_page)))
        if per_page < 1:
            per_page = default_per_page
    except Exception:
        per_page = default_per_page
    offset = (page - 1) * per_page
    return page, per_page, offset



@router.get('/admin/users')
async def list_users(request: Request, user=Depends(require_admin)):
    # Support optional server-side filtering, search and pagination via query params
    qs = request.query_params
    flt = qs.get('filter', 'all')
    q = qs.get('q')
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
    return {
        'users': users,
        'total': total,
        'page': page,
        'per_page': per_page,
        'banned_ids': banned_ids,
    }


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
    page, per_page, offset = _parse_pagination(request)
    q = request.query_params.get('q')

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
            {
                'id': r[0],
                'owner_id': r[1],
                'name': r[2],
                'created_at': r[3],
                'owner_username': r[4],
                'member_count': r[5],
            }
            for r in rows
        ]

    return {'rooms': rooms, 'total': total, 'page': page, 'per_page': per_page}


@router.get('/admin/banned')
async def list_banned(request: Request, user=Depends(require_admin)):
    """List banned users with optional pagination: ?page=&per_page="""
    page, per_page, offset = _parse_pagination(request)
    # read optional search query
    q = request.query_params.get('q')

    async with aiosqlite.connect(DB) as db:
        # total count for pager (respect q when present)
        if q:
            if q.isdigit():
                cur = await db.execute('SELECT COUNT(*) FROM bans WHERE banned_id = ?', (int(q),))
            else:
                cur = await db.execute(
                    'SELECT COUNT(*) FROM bans b LEFT JOIN users u ON b.banned_id = u.id WHERE u.username LIKE ? OR u.email LIKE ?',
                    (f'%{q}%', f'%{q}%'),
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
                    'ORDER BY b.id DESC LIMIT ? OFFSET ?',
                    (int(q), per_page, offset),
                )
            else:
                cur = await db.execute(
                    'SELECT b.id, b.banned_id, u.username, u.email, b.banner_id, b.created_at '
                    'FROM bans b LEFT JOIN users u ON b.banned_id = u.id '
                    'WHERE u.username LIKE ? OR u.email LIKE ? '
                    'ORDER BY b.id DESC LIMIT ? OFFSET ?',
                    (f'%{q}%', f'%{q}%', per_page, offset),
                )
        else:
            cur = await db.execute(
                'SELECT b.id, b.banned_id, u.username, u.email, b.banner_id, b.created_at '
                'FROM bans b LEFT JOIN users u ON b.banned_id = u.id '
                'ORDER BY b.id DESC LIMIT ? OFFSET ?',
                (per_page, offset),
            )
        rows = await cur.fetchall()
        banned = [
            {
                'id': r[0],
                'banned_id': r[1],
                'username': r[2],
                'email': r[3],
                'banner_id': r[4],
                'created_at': r[5],
            }
            for r in rows
        ]

    return {'banned': banned, 'total': total, 'page': page, 'per_page': per_page}


@router.post('/admin/ban_user')
async def ban_user(request: Request, user=Depends(require_admin)):
    body = await request.json()
    uid = body.get('user_id') or body.get('id')
    if not uid:
        raise HTTPException(status_code=400, detail='user_id required')
    # delegate to service
    await admin_service.ban_user(user['id'], uid)
    return {'ok': True}


@router.post('/admin/unban_user')
async def unban_user(request: Request, user=Depends(require_admin)):
    body = await request.json()
    uid = body.get('user_id') or body.get('id')
    if not uid:
        raise HTTPException(status_code=400, detail='user_id required')
    await admin_service.unban_user(uid)
    return {'ok': True}


@router.post('/admin/make_admin')
async def make_admin(request: Request, user=Depends(require_admin)):
    body = await request.json()
    uid = body.get('user_id') or body.get('id')
    if not uid:
        raise HTTPException(status_code=400, detail='user id required')
    await admin_service.set_admin(uid, True)
    return {'ok': True}


@router.post('/admin/revoke_admin')
async def revoke_admin(request: Request, user=Depends(require_admin)):
    body = await request.json()
    uid = body.get('user_id') or body.get('id')
    if not uid:
        raise HTTPException(status_code=400, detail='user id required')
    await admin_service.set_admin(uid, False)
    return {'ok': True}


@router.post('/admin/delete_room')
async def admin_delete_room(request: Request, user=Depends(require_admin)):
    body = await request.json()
    rid = body.get('room_id') or body.get('id')
    if not rid:
        raise HTTPException(status_code=400, detail='room_id required')
    # delegate DB-heavy cleanup to service
    deleted = await admin_service.delete_room_and_cleanup(rid)
    return {'ok': True, 'deleted': deleted}


@router.post('/admin/delete_message')
async def admin_delete_message(request: Request, user=Depends(require_admin)):
    body = await request.json()
    mid = body.get('message_id') or body.get('id')
    if not mid:
        raise HTTPException(status_code=400, detail='message_id required')
    deleted = await admin_service.delete_message_and_cleanup(mid)
    return {'ok': True, 'deleted': deleted}


@router.get('/admin/messages')
async def admin_list_messages(request: Request, user=Depends(require_admin)):
    """List messages for admin moderation. Supports optional search `q`, `page`, `per_page`, and `room_id`."""
    qs = request.query_params
    q = qs.get('q')
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
            {
                'id': r[0],
                'room_id': r[1],
                'room_name': r[2],
                'user_id': r[3],
                'username': r[4],
                'text': r[5],
                'created_at': r[6],
            }
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
