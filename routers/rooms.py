from fastapi import APIRouter, Request, HTTPException, Depends
import aiosqlite
import time
from db import DB
from core.utils import require_auth
import logging
logging.getLogger(__name__).info('routers.rooms module loaded from %s', __file__)

router = APIRouter()


@router.post('/rooms')
async def create_room(request: Request, user=Depends(require_auth)):
    body = await request.json()
    name = body.get('name')
    description = body.get('description', '')
    visibility = body.get('visibility', 'public')
    if not name:
        raise HTTPException(status_code=400, detail='room name required')
    if visibility not in ('public', 'private'):
        raise HTTPException(status_code=400, detail='visibility must be public or private')
    async with aiosqlite.connect(DB) as db:
        try:
            await db.execute('INSERT INTO rooms (owner_id, name, description, visibility, created_at) VALUES (?, ?, ?, ?, ?)',
                             (user['id'], name, description, visibility, int(time.time())))
            await db.commit()
        except aiosqlite.IntegrityError:
            raise HTTPException(status_code=409, detail='room name taken')
        cur = await db.execute('SELECT id, owner_id, name, description, visibility, created_at FROM rooms WHERE name = ?', (name,))
        row = await cur.fetchone()
        room = {'id': row[0], 'owner_id': row[1], 'name': row[2], 'description': row[3], 'visibility': row[4], 'created_at': row[5]}
        # add owner as member and admin
        await db.execute('INSERT OR IGNORE INTO memberships (room_id, user_id, created_at) VALUES (?, ?, ?)', (room['id'], user['id'], int(time.time())))
        await db.execute('INSERT OR IGNORE INTO room_admins (room_id, user_id, created_at) VALUES (?, ?, ?)', (room['id'], user['id'], int(time.time())))
        await db.commit()
        return {'room': room}


@router.get('/rooms')
async def list_rooms(request: Request, q: str = None, limit: int = 50, offset: int = 0, visibility: str = 'public'):
    """List public rooms. Supports simple search via `q` (substring match on name or description).

    Returns each room with a `member_count` field.
    """
    async with aiosqlite.connect(DB) as db:
        params = []

        # We'll compute a WHERE clause based on requested visibility. By default
        # list only public rooms. Clients may request `visibility=private` or
        # `visibility=all`. Private rooms are only visible to authenticated
        # members; anonymous requests will see no private rooms.
        visibility = (visibility or 'public')
        if visibility not in ('public', 'private', 'all'):
            raise HTTPException(status_code=400, detail='visibility must be public, private, or all')

    # Try to resolve an optional authenticated user from the request. We prefer
        # returning is_member explicitly (false) for anonymous requests for
        # predictable client behavior.
        user = None
        try:
            auth = request.headers.get('authorization')
            cookie_token = request.cookies.get('token')
            token_val = None
            if auth:
                token_val = auth.replace('Bearer ', '')
            elif cookie_token:
                token_val = cookie_token
            if token_val:
                try:
                    from core.utils import verify_token, session_exists
                    data = verify_token(token_val)
                    jti = data.get('jti')
                    if jti and await session_exists(jti):
                        user = data
                except Exception:
                    user = None
        except Exception:
            user = None

        # After resolving user, construct the WHERE clause so we can safely
        # include any user id parameters needed by the WHERE.

        # build visibility-aware WHERE clause
        where = ''
        where_params = []
        if visibility == 'public':
            where = "WHERE visibility = 'public'"
        elif visibility == 'private':
            # only return private rooms the current user is a member of
            if user and user.get('id'):
                where = "WHERE visibility = 'private' AND EXISTS(SELECT 1 FROM memberships m3 WHERE m3.room_id = r.id AND m3.user_id = ?)"
                where_params = [user.get('id')]
            else:
                # anonymous or unauthenticated: empty set
                where = "WHERE 0"
        else:  # visibility == 'all'
            if user and user.get('id'):
                # show public rooms and private rooms where the user is a member
                where = "WHERE (visibility = 'public' OR (visibility = 'private' AND EXISTS(SELECT 1 FROM memberships m3 WHERE m3.room_id = r.id AND m3.user_id = ?)))"
                where_params = [user.get('id')]
            else:
                where = "WHERE visibility = 'public'"

        # apply q search if present
        if q:
            where += " AND (name LIKE ? OR description LIKE ?)"
            pattern = f"%{q}%"
            where_params.extend([pattern, pattern])

        # we'll append limit/offset after any user params
        # join memberships to compute member counts. Include an `is_member` column
        # which is either 0 (anonymous/no membership) or computed via EXISTS.
        if user and user.get('id'):
            member_expr = "EXISTS(SELECT 1 FROM memberships m2 WHERE m2.room_id = r.id AND m2.user_id = ?) as is_member"
            params_for_member = [user.get('id')]
        else:
            member_expr = "0 as is_member"
            params_for_member = []

        # final param ordering: where_params (may include user id and/or q patterns),
        # then params_for_member (user id for is_member if present), then limit/offset
        params = []
        params.extend(where_params)
        params.extend(params_for_member)
        params.extend([limit, offset])

        sql = f"""
        SELECT r.id, r.owner_id, r.name, r.description, r.visibility, r.created_at,
               COUNT(m.id) as member_count, {member_expr}
        FROM rooms r
        LEFT JOIN memberships m ON m.room_id = r.id
        {where}
        GROUP BY r.id
        ORDER BY r.created_at DESC
        LIMIT ? OFFSET ?
        """
        cur = await db.execute(sql, params)
        rows = await cur.fetchall()
        # compute total count matching the where clause (without limit/offset)
        count_sql = f"SELECT COUNT(1) FROM rooms r {where}"
        count_params = []
        # where_params contains the q patterns (and possibly a user id) in order
        if where_params:
            count_params.extend(where_params)
        cur2 = await db.execute(count_sql, count_params)
        total_row = await cur2.fetchone()
        total = total_row[0] if total_row else None
        rooms = [
            {
                'id': r[0],
                'owner_id': r[1],
                'name': r[2],
                'description': r[3],
                'visibility': r[4],
                'created_at': r[5],
                'member_count': r[6],
                'is_member': bool(r[7]) if len(r) > 7 else False,
            }
            for r in rows
        ]

        # Enrich rooms with owner (rich object when available) and admins list/info
        if rooms:
            room_ids = [r['id'] for r in rooms]
            placeholders = ','.join(['?'] * len(room_ids))
            # fetch admin mappings for these rooms
            cur = await db.execute(f'SELECT room_id, user_id FROM room_admins WHERE room_id IN ({placeholders})', tuple(room_ids))
            admin_rows = await cur.fetchall()
            admins_map = {}
            admin_user_ids = set()
            for ar in admin_rows:
                rid, uid = ar[0], ar[1]
                admins_map.setdefault(rid, []).append(uid)
                admin_user_ids.add(uid)

            # collect owner ids as well
            owner_ids = set(r.get('owner_id') for r in rooms if r.get('owner_id'))
            user_ids = set()
            user_ids.update(owner_ids)
            user_ids.update(admin_user_ids)

            users_map = {}
            if user_ids:
                placeholders2 = ','.join(['?'] * len(user_ids))
                q = f'SELECT id, username, email FROM users WHERE id IN ({placeholders2})'
                cur = await db.execute(q, tuple(user_ids))
                user_rows = await cur.fetchall()
                for ur in user_rows:
                    users_map[ur[0]] = {'id': ur[0], 'username': ur[1], 'email': ur[2]}

            for rm in rooms:
                rid = rm['id']
                rm_admins = admins_map.get(rid, [])
                rm['admins'] = rm_admins
                rm['admins_info'] = [users_map.get(u) or {'id': u} for u in rm_admins]
                rm_owner_obj = users_map.get(rm.get('owner_id')) if rm.get('owner_id') else None
                rm['owner_obj'] = rm_owner_obj
                rm['owner'] = rm_owner_obj or rm.get('owner_id')

    return {'rooms': rooms, 'total': total}


@router.get('/rooms/{room_id}')
async def get_room(room_id: int, user=Depends(require_auth)):
    async with aiosqlite.connect(DB) as db:
        cur = await db.execute('SELECT id, owner_id, name, description, visibility, created_at FROM rooms WHERE id = ?', (room_id,))
        row = await cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail='room not found')
        room = {'id': row[0], 'owner_id': row[1], 'name': row[2], 'description': row[3], 'visibility': row[4], 'created_at': row[5]}
        # check ban
        cur = await db.execute('SELECT id FROM room_bans WHERE room_id = ? AND banned_id = ?', (room_id, user['id']))
        if await cur.fetchone():
            raise HTTPException(status_code=403, detail='banned from room')
        # check membership if private
        if room['visibility'] == 'private':
            cur = await db.execute('SELECT id FROM memberships WHERE room_id = ? AND user_id = ?', (room_id, user['id']))
            m = await cur.fetchone()
            if not m:
                raise HTTPException(status_code=403, detail='private room')
        # list admins and members (ids)
        cur = await db.execute('SELECT user_id FROM room_admins WHERE room_id = ?', (room_id,))
        admins = [r[0] for r in await cur.fetchall()]
        cur = await db.execute('SELECT user_id FROM memberships WHERE room_id = ?', (room_id,))
        members = [r[0] for r in await cur.fetchall()]
        # fetch ban rows with banner information for richer detail
        cur = await db.execute('SELECT banned_id, banner_id, created_at FROM room_bans WHERE room_id = ?', (room_id,))
        ban_rows = await cur.fetchall()
        bans = [r[0] for r in ban_rows]
        bans_detail = [{'banned_id': r[0], 'banner_id': r[1], 'created_at': r[2]} for r in ban_rows]

        # fetch user info for owner/admins/members/banned users to provide richer data
        user_ids = set()
        if room.get('owner_id'):
            user_ids.add(room.get('owner_id'))
        user_ids.update(admins)
        user_ids.update(members)
        user_ids.update(bans)
        users_map = {}
        if user_ids:
            placeholders = ','.join(['?'] * len(user_ids))
            q = f'SELECT id, username, email FROM users WHERE id IN ({placeholders})'
            cur = await db.execute(q, tuple(user_ids))
            rows = await cur.fetchall()
            for r in rows:
                users_map[r[0]] = { 'id': r[0], 'username': r[1], 'email': r[2] }

        # keep backward-compatible id lists, and add richer objects
    room.update({'admins': admins, 'members': members, 'bans': bans, 'bans_detail': bans_detail})
    # richer owner object for convenience; keep owner_id for backward compatibility
    room['owner_obj'] = users_map.get(room.get('owner_id')) if room.get('owner_id') else None
    # set a friendly `owner` field to the richer owner object when available
    room['owner'] = room['owner_obj'] or room.get('owner_id')
    room['admins_info'] = [users_map.get(u) or {'id': u} for u in admins]
    room['members_info'] = [users_map.get(u) or {'id': u} for u in members]
    room['bans_info'] = [users_map.get(u) or {'id': u} for u in bans]
    # provide a simple banned count to help clients avoid computing length
    try:
        room['banned_count'] = len(bans)
    except Exception:
        room['banned_count'] = 0
        
    return {'room': room}


@router.post('/rooms/{room_id}/join')
async def join_room(room_id: int, user=Depends(require_auth)):
    async with aiosqlite.connect(DB) as db:
        cur = await db.execute('SELECT visibility FROM rooms WHERE id = ?', (room_id,))
        row = await cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail='room not found')
        visibility = row[0]
        # check ban
        cur = await db.execute('SELECT id FROM room_bans WHERE room_id = ? AND banned_id = ?', (room_id, user['id']))
        if await cur.fetchone():
            raise HTTPException(status_code=403, detail='banned from room')
        if visibility == 'private':
            raise HTTPException(status_code=403, detail='private room')
        # Avoid duplicate memberships: check first, then insert if absent. If
        # historical duplicates exist (pre-index), remove them keeping the
        # earliest entry to normalize the DB. This also serves as a defensive
        # measure in case a race created more than one row.
        cur = await db.execute('SELECT id FROM memberships WHERE room_id = ? AND user_id = ?', (room_id, user['id']))
        rows = await cur.fetchall()
        if rows and len(rows) > 0:
            # if there is at least one existing membership, delete any extras
            if len(rows) > 1:
                ids = [str(r[0]) for r in rows]
                # delete all but the smallest id (earliest)
                keep = min(int(r[0]) for r in rows)
                await db.execute('DELETE FROM memberships WHERE room_id = ? AND user_id = ? AND id != ?', (room_id, user['id'], keep))
                await db.commit()
            return {'ok': True, 'already_member': True}
        # insert a fresh membership
        try:
            await db.execute('INSERT INTO memberships (room_id, user_id, created_at) VALUES (?, ?, ?)', (room_id, user['id'], int(time.time())))
            await db.commit()
            # Defensive cleanup: ensure no historical duplicates remain for any reason
            try:
                await db.execute('DELETE FROM memberships WHERE id NOT IN (SELECT MIN(id) FROM memberships GROUP BY room_id, user_id)')
                await db.commit()
            except Exception:
                pass
        except Exception:
            # In the unlikely event of a race leading to a unique constraint
            # violation, clean up duplicates and treat as idempotent success.
            try:
                cur = await db.execute('SELECT id FROM memberships WHERE room_id = ? AND user_id = ?', (room_id, user['id']))
                rows2 = await cur.fetchall()
                if rows2 and len(rows2) > 1:
                    keep = min(int(r[0]) for r in rows2)
                    await db.execute('DELETE FROM memberships WHERE room_id = ? AND user_id = ? AND id != ?', (room_id, user['id'], keep))
                    await db.commit()
                return {'ok': True, 'already_member': True}
            except Exception:
                # give up but return a generic success to avoid leaking DB errors
                return {'ok': True, 'already_member': True}
        return {'ok': True, 'already_member': False}


@router.post('/rooms/{room_id}/leave')
async def leave_room(room_id: int, user=Depends(require_auth)):
    async with aiosqlite.connect(DB) as db:
        # owner cannot leave their own room
        cur = await db.execute('SELECT owner_id FROM rooms WHERE id = ?', (room_id,))
        row = await cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail='room not found')
        owner_id = row[0]
        if owner_id == user['id']:
            raise HTTPException(status_code=403, detail='owner cannot leave room')
        await db.execute('DELETE FROM memberships WHERE room_id = ? AND user_id = ?', (room_id, user['id']))
        # also remove from admins if present
        await db.execute('DELETE FROM room_admins WHERE room_id = ? AND user_id = ?', (room_id, user['id']))
        await db.commit()
        return {'ok': True}



@router.delete('/rooms/{room_id}')
async def delete_room(room_id: int, user=Depends(require_auth)):
    """Owner may delete their room. Deleting cascades via DB foreign keys."""
    async with aiosqlite.connect(DB) as db:
        cur = await db.execute('SELECT owner_id FROM rooms WHERE id = ?', (room_id,))
        row = await cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail='room not found')
        owner_id = row[0]
        if owner_id != user['id']:
            raise HTTPException(status_code=403, detail='not authorized')
        # delete associated files from disk (if tracked in room_files)
        cur = await db.execute('SELECT id, path FROM room_files WHERE room_id = ?', (room_id,))
        rows = await cur.fetchall()
        import os

        for r in rows:
            fid, p = r[0], r[1]
            try:
                # handle both absolute and relative paths
                if not os.path.isabs(p):
                    p = os.path.join('uploads', p)
                if os.path.exists(p):
                    os.remove(p)
            except Exception:
                # ignore file deletion errors but continue
                pass
        # remove DB rows for files (cascade would remove on room delete, but clean explicitly)
        await db.execute('DELETE FROM room_files WHERE room_id = ?', (room_id,))
        # delete messages, memberships, admins, bans explicitly to be robust
        await db.execute('DELETE FROM messages WHERE room_id = ?', (room_id,))
        await db.execute('DELETE FROM memberships WHERE room_id = ?', (room_id,))
        await db.execute('DELETE FROM room_admins WHERE room_id = ?', (room_id,))
        await db.execute('DELETE FROM room_bans WHERE room_id = ?', (room_id,))
        # now delete the room
        await db.execute('DELETE FROM rooms WHERE id = ?', (room_id,))
        await db.commit()
        return {'ok': True}


def _is_owner_or_admin(db, room_id: int, user_id: int):
    async def inner():
        cur = await db.execute('SELECT owner_id FROM rooms WHERE id = ?', (room_id,))
        row = await cur.fetchone()
        if not row:
            return False
        if row[0] == user_id:
            return True
        cur = await db.execute('SELECT id FROM room_admins WHERE room_id = ? AND user_id = ?', (room_id, user_id))
        return bool(await cur.fetchone())
    return inner


@router.post('/rooms/{room_id}/admins/add')
async def add_admin(room_id: int, request: Request, user=Depends(require_auth)):
    body = await request.json()
    uid = body.get('user_id')
    if not uid:
        raise HTTPException(status_code=400, detail='user_id required')
    async with aiosqlite.connect(DB) as db:
        checker = _is_owner_or_admin(db, room_id, user['id'])
        if not await checker():
            raise HTTPException(status_code=403, detail='not authorized')
        await db.execute('INSERT OR IGNORE INTO room_admins (room_id, user_id, created_at) VALUES (?, ?, ?)', (room_id, uid, int(time.time())))
        await db.commit()
        return {'ok': True}


@router.post('/rooms/{room_id}/admins/remove')
async def remove_admin(room_id: int, request: Request, user=Depends(require_auth)):
    body = await request.json()
    uid = body.get('user_id')
    if not uid:
        raise HTTPException(status_code=400, detail='user_id required')
    async with aiosqlite.connect(DB) as db:
        checker = _is_owner_or_admin(db, room_id, user['id'])
        if not await checker():
            raise HTTPException(status_code=403, detail='not authorized')
        # owner must always remain an admin
        cur = await db.execute('SELECT owner_id FROM rooms WHERE id = ?', (room_id,))
        row = await cur.fetchone()
        if row and row[0] == uid:
            raise HTTPException(status_code=403, detail='cannot remove owner admin status')
        await db.execute('DELETE FROM room_admins WHERE room_id = ? AND user_id = ?', (room_id, uid))
        await db.commit()
        return {'ok': True}


@router.post('/rooms/{room_id}/ban')
async def ban_user(room_id: int, request: Request, user=Depends(require_auth)):
    body = await request.json()
    uid = body.get('user_id')
    if not uid:
        raise HTTPException(status_code=400, detail='user_id required')
    async with aiosqlite.connect(DB) as db:
        checker = _is_owner_or_admin(db, room_id, user['id'])
        if not await checker():
            raise HTTPException(status_code=403, detail='not authorized')
        # prevent banning the owner
        cur = await db.execute('SELECT owner_id FROM rooms WHERE id = ?', (room_id,))
        row = await cur.fetchone()
        if row and row[0] == uid:
            raise HTTPException(status_code=403, detail='cannot ban owner')
        # record who banned the user
        await db.execute('INSERT OR IGNORE INTO room_bans (room_id, banned_id, banner_id, created_at) VALUES (?, ?, ?, ?)', (room_id, uid, user['id'], int(time.time())))
        # remove from memberships and admins
        await db.execute('DELETE FROM memberships WHERE room_id = ? AND user_id = ?', (room_id, uid))
        await db.execute('DELETE FROM room_admins WHERE room_id = ? AND user_id = ?', (room_id, uid))
        await db.commit()
        return {'ok': True}


@router.post('/rooms/{room_id}/unban')
async def unban_user(room_id: int, request: Request, user=Depends(require_auth)):
    body = await request.json()
    uid = body.get('user_id')
    if not uid:
        raise HTTPException(status_code=400, detail='user_id required')
    async with aiosqlite.connect(DB) as db:
        checker = _is_owner_or_admin(db, room_id, user['id'])
        if not await checker():
            raise HTTPException(status_code=403, detail='not authorized')
        await db.execute('DELETE FROM room_bans WHERE room_id = ? AND banned_id = ?', (room_id, uid))
        await db.commit()
        return {'ok': True}


@router.get('/rooms/{room_id}/bans')
async def list_bans(room_id: int, user=Depends(require_auth)):
    """List banned users for a room along with who banned them. Admins/owner only."""
    async with aiosqlite.connect(DB) as db:
        checker = _is_owner_or_admin(db, room_id, user['id'])
        if not await checker():
            raise HTTPException(status_code=403, detail='not authorized')
        cur = await db.execute('SELECT banned_id, banner_id, created_at FROM room_bans WHERE room_id = ?', (room_id,))
        rows = await cur.fetchall()
        bans = [{'banned_id': r[0], 'banner_id': r[1], 'created_at': r[2]} for r in rows]
        return {'bans': bans}


@router.post('/rooms/{room_id}/members/remove')
async def remove_member(room_id: int, request: Request, user=Depends(require_auth)):
    """Owner or admin may remove a member from the room."""
    body = await request.json()
    uid = body.get('user_id')
    if not uid:
        raise HTTPException(status_code=400, detail='user_id required')
    async with aiosqlite.connect(DB) as db:
        checker = _is_owner_or_admin(db, room_id, user['id'])
        if not await checker():
            raise HTTPException(status_code=403, detail='not authorized')
        # owner may remove anyone; admins may not remove the owner
        cur = await db.execute('SELECT owner_id FROM rooms WHERE id = ?', (room_id,))
        row = await cur.fetchone()
        if row and row[0] == uid and row[0] != user['id']:
            raise HTTPException(status_code=403, detail='cannot remove owner')
        # treat removal as a ban: remove membership/admin and add to room_bans
        await db.execute('DELETE FROM memberships WHERE room_id = ? AND user_id = ?', (room_id, uid))
        await db.execute('DELETE FROM room_admins WHERE room_id = ? AND user_id = ?', (room_id, uid))
        # record who removed (banner)
        await db.execute('INSERT OR IGNORE INTO room_bans (room_id, banned_id, banner_id, created_at) VALUES (?, ?, ?, ?)', (room_id, uid, user['id'], int(time.time())))
        await db.commit()
        return {'ok': True}


@router.get('/rooms/{room_id}/files')
async def list_room_files(room_id: int, user=Depends(require_auth)):
    """List files tracked for a room. Private rooms require membership. Banned users blocked."""
    async with aiosqlite.connect(DB) as db:
        # check room exists
        cur = await db.execute('SELECT visibility FROM rooms WHERE id = ?', (room_id,))
        row = await cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail='room not found')
        visibility = row[0]
        # check ban
        cur = await db.execute('SELECT id FROM room_bans WHERE room_id = ? AND banned_id = ?', (room_id, user['id']))
        if await cur.fetchone():
            raise HTTPException(status_code=403, detail='banned from room')
        # check membership if private
        if visibility == 'private':
            cur = await db.execute('SELECT id FROM memberships WHERE room_id = ? AND user_id = ?', (room_id, user['id']))
            if not await cur.fetchone():
                raise HTTPException(status_code=403, detail='private room')
        cur = await db.execute('SELECT id, path, created_at FROM room_files WHERE room_id = ?', (room_id,))
        rows = await cur.fetchall()
        files = [{'id': r[0], 'path': r[1], 'created_at': r[2]} for r in rows]
        return {'files': files}


from fastapi.responses import FileResponse
from fastapi import UploadFile, File, Form
from typing import Optional
import os
import uuid
import time as _time

# Use TEST_UPLOAD_DIR when running tests (set in .env.test), otherwise default to 'uploads'
UPLOADS_DIR = os.path.join(os.getcwd(), os.getenv('TEST_UPLOAD_DIR', 'uploads'))
os.makedirs(UPLOADS_DIR, exist_ok=True)


@router.get('/rooms/{room_id}/files/{file_id}')
async def get_room_file(room_id: int, file_id: int, user=Depends(require_auth)):
    """Serve a file for a room with permission checks."""
    async with aiosqlite.connect(DB) as db:
        cur = await db.execute('SELECT path FROM room_files WHERE id = ? AND room_id = ?', (file_id, room_id))
        row = await cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail='file not found')
        path = row[0]
        # check ban
        cur = await db.execute('SELECT id FROM room_bans WHERE room_id = ? AND banned_id = ?', (room_id, user['id']))
        if await cur.fetchone():
            raise HTTPException(status_code=403, detail='banned from room')
        # check room visibility and require membership only for private rooms
        cur = await db.execute('SELECT visibility FROM rooms WHERE id = ?', (room_id,))
        r2 = await cur.fetchone()
        if not r2:
            raise HTTPException(status_code=404, detail='room not found')
        if r2[0] == 'private':
            cur = await db.execute('SELECT id FROM memberships WHERE room_id = ? AND user_id = ?', (room_id, user['id']))
            if not await cur.fetchone():
                raise HTTPException(status_code=403, detail='private room')
        # resolve path: prefer UPLOADS_DIR (TEST_UPLOAD_DIR) but fall back to legacy 'uploads' for existing files
        if os.path.isabs(path):
            p = path
        else:
            p = os.path.join(UPLOADS_DIR, path)
            if not os.path.exists(p):
                # fallback to legacy uploads/ location
                legacy = os.path.join(os.getcwd(), 'uploads', path)
                if os.path.exists(legacy):
                    p = legacy
        if not os.path.exists(p):
            raise HTTPException(status_code=404, detail='file not found on disk')
        return FileResponse(p)



@router.post('/rooms/{room_id}/files')
async def upload_room_file(room_id: int, file: UploadFile = File(...), comment: Optional[str] = Form(None), user=Depends(require_auth)):
    """Upload an attachment to a room (images or arbitrary files)."""
    async with aiosqlite.connect(DB) as db:
        cur = await db.execute('SELECT visibility FROM rooms WHERE id = ?', (room_id,))
        row = await cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail='room not found')
        # check ban
        cur = await db.execute('SELECT 1 FROM room_bans WHERE room_id = ? AND banned_id = ?', (room_id, user['id']))
        if await cur.fetchone():
            raise HTTPException(status_code=403, detail='banned from room')
        # check membership if private
        if row[0] == 'private':
            cur = await db.execute('SELECT 1 FROM memberships WHERE room_id = ? AND user_id = ?', (room_id, user['id']))
            if not await cur.fetchone():
                raise HTTPException(status_code=403, detail='private room')
        uploads_dir = UPLOADS_DIR
        safe_name = f"{int(_time.time())}_{uuid.uuid4().hex}_{file.filename}"
        dest_path = os.path.join(uploads_dir, safe_name)
        contents = await file.read()
        with open(dest_path, 'wb') as fh:
            fh.write(contents)
        await db.execute('INSERT INTO room_files (room_id, path, original_filename, comment, created_at) VALUES (?, ?, ?, ?, ?)', (room_id, safe_name, file.filename, comment, int(_time.time())))
        await db.commit()
        cur = await db.execute('SELECT id, room_id, path, original_filename, comment, created_at FROM room_files WHERE rowid = last_insert_rowid()')
        r = await cur.fetchone()
        return {'file': {'id': r[0], 'room_id': r[1], 'path': r[2], 'original_filename': r[3], 'comment': r[4], 'created_at': r[5]}}


@router.post('/rooms/{room_id}/files/paste')
async def paste_room_file(room_id: int, request: Request, user=Depends(require_auth)):
    """Accept pasted file data (data URL or raw base64) in JSON and store as a room attachment.

    Body: { filename: str, data: str }
    """
    body = await request.json()
    filename = body.get('filename')
    data = body.get('data')
    if not filename or not data:
        raise HTTPException(status_code=400, detail='filename and data required')
    if data.startswith('data:'):
        try:
            header, b64 = data.split(',', 1)
        except ValueError:
            raise HTTPException(status_code=400, detail='invalid data url')
    else:
        b64 = data
    import base64

    try:
        raw = base64.b64decode(b64)
    except Exception:
        raise HTTPException(status_code=400, detail='invalid base64 data')

    async with aiosqlite.connect(DB) as db:
        cur = await db.execute('SELECT visibility FROM rooms WHERE id = ?', (room_id,))
        row = await cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail='room not found')
        # check ban
        cur = await db.execute('SELECT 1 FROM room_bans WHERE room_id = ? AND banned_id = ?', (room_id, user['id']))
        if await cur.fetchone():
            raise HTTPException(status_code=403, detail='banned from room')
        # check membership if private
        if row[0] == 'private':
            cur = await db.execute('SELECT 1 FROM memberships WHERE room_id = ? AND user_id = ?', (room_id, user['id']))
            if not await cur.fetchone():
                raise HTTPException(status_code=403, detail='private room')
        uploads_dir = UPLOADS_DIR
        safe_name = f"{int(_time.time())}_{uuid.uuid4().hex}_{filename}"
        dest_path = os.path.join(uploads_dir, safe_name)
        with open(dest_path, 'wb') as fh:
            fh.write(raw)
        # optional comment passed in JSON
        comment = body.get('comment')
        await db.execute('INSERT INTO room_files (room_id, path, original_filename, comment, created_at) VALUES (?, ?, ?, ?, ?)', (room_id, safe_name, filename, comment, int(_time.time())))
        await db.commit()
        cur = await db.execute('SELECT id, room_id, path, original_filename, comment, created_at FROM room_files WHERE rowid = last_insert_rowid()')
        r = await cur.fetchone()
        return {'file': {'id': r[0], 'room_id': r[1], 'path': r[2], 'original_filename': r[3], 'comment': r[4], 'created_at': r[5]}}


@router.post('/rooms/{room_id}/messages_with_file')
async def post_room_message_with_file(room_id: int, file: UploadFile = File(None), text: Optional[str] = Form(None), reply_to: Optional[int] = Form(None), comment: Optional[str] = Form(None), user=Depends(require_auth)):
    """Atomic endpoint to create a room message and optionally attach a file in one request."""
    async with aiosqlite.connect(DB) as db:
        cur = await db.execute('SELECT visibility FROM rooms WHERE id = ?', (room_id,))
        row = await cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail='room not found')
        visibility = row[0]
        # check ban
        cur = await db.execute('SELECT id FROM room_bans WHERE room_id = ? AND banned_id = ?', (room_id, user['id']))
        if await cur.fetchone():
            raise HTTPException(status_code=403, detail='banned from room')
        if visibility == 'private':
            cur = await db.execute('SELECT id FROM memberships WHERE room_id = ? AND user_id = ?', (room_id, user['id']))
            if not await cur.fetchone():
                raise HTTPException(status_code=403, detail='private room')
        # enforce text size limit (same rule as post_room_message)
        if text is not None:
            try:
                size = len(text.encode('utf-8'))
            except Exception:
                raise HTTPException(status_code=400, detail='invalid text encoding')
            if size > 3 * 1024:
                raise HTTPException(status_code=400, detail='text too long (max 3KB)')
        # validate reply_to if provided
        if reply_to:
            cur = await db.execute('SELECT id FROM messages WHERE id = ? AND room_id = ?', (reply_to, room_id))
            if not await cur.fetchone():
                raise HTTPException(status_code=400, detail='invalid reply_to')
        # insert message
        await db.execute('INSERT INTO messages (room_id, user_id, text, reply_to, created_at) VALUES (?, ?, ?, ?, ?)', (room_id, user['id'], text or '', reply_to, int(_time.time())))
        await db.commit()
        cur = await db.execute('SELECT id, room_id, user_id, text, reply_to, created_at FROM messages WHERE rowid = last_insert_rowid()')
        rmsg = await cur.fetchone()
        msg = {'id': rmsg[0], 'room_id': rmsg[1], 'user_id': rmsg[2], 'text': rmsg[3], 'reply_to': rmsg[4], 'created_at': rmsg[5]}
        # attach reply preview if reply_to is present
        if msg.get('reply_to'):
            cur = await db.execute('SELECT id, user_id, text, created_at FROM messages WHERE id = ? AND room_id = ?', (msg['reply_to'], room_id))
            rr = await cur.fetchone()
            if rr:
                msg['reply'] = {'id': rr[0], 'user_id': rr[1], 'text': rr[2], 'created_at': rr[3]}
        file_meta = None
        if file:
            uploads_dir = UPLOADS_DIR
            os.makedirs(uploads_dir, exist_ok=True)
            safe_name = f"{int(_time.time())}_{uuid.uuid4().hex}_{file.filename}"
            dest_path = os.path.join(uploads_dir, safe_name)
            contents = await file.read()
            with open(dest_path, 'wb') as fh:
                fh.write(contents)
            # insert into room_files and message_files
            await db.execute('INSERT INTO room_files (room_id, path, original_filename, comment, created_at) VALUES (?, ?, ?, ?, ?)', (room_id, safe_name, file.filename, comment, int(_time.time())))
            await db.commit()
            cur = await db.execute('SELECT id, room_id, path, original_filename, comment, created_at FROM room_files WHERE rowid = last_insert_rowid()')
            r = await cur.fetchone()
            room_file_id = r[0]
            await db.execute('INSERT INTO message_files (message_id, room_file_id, created_at) VALUES (?, ?, ?)', (msg['id'], room_file_id, int(_time.time())))
            await db.commit()
            file_meta = {'id': room_file_id, 'room_id': r[1], 'path': r[2], 'original_filename': r[3], 'comment': r[4], 'created_at': r[5], 'url': f"/rooms/{room_id}/files/{room_file_id}"}
        return {'message': msg, 'file': file_meta}


@router.delete('/rooms/{room_id}/messages/{message_id}')
async def delete_message(room_id: int, message_id: int, user=Depends(require_auth)):
    """Admins/owner may delete messages in a room."""
    async with aiosqlite.connect(DB) as db:
        # allow deletion if requester is the message author or an owner/admin
        # ensure message exists and belongs to room and fetch author
        cur = await db.execute('SELECT user_id FROM messages WHERE id = ? AND room_id = ?', (message_id, room_id))
        row = await cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail='message not found')
        author_id = row[0]
        checker = _is_owner_or_admin(db, room_id, user['id'])
        is_admin = await checker()
        if author_id != user['id'] and not is_admin:
            raise HTTPException(status_code=403, detail='not authorized')
        await db.execute('DELETE FROM messages WHERE id = ? AND room_id = ?', (message_id, room_id))
        await db.commit()
        return {'ok': True}


@router.post('/rooms/{room_id}/members/add')
async def add_member(room_id: int, request: Request, user=Depends(require_auth)):
    """Owner or admin can add a user as a member (useful for private rooms). Body: { user_id }"""
    body = await request.json()
    uid = body.get('user_id')
    if not uid:
        raise HTTPException(status_code=400, detail='user_id required')
    async with aiosqlite.connect(DB) as db:
        checker = _is_owner_or_admin(db, room_id, user['id'])
        if not await checker():
            raise HTTPException(status_code=403, detail='not authorized')
        # don't add if banned
        cur = await db.execute('SELECT id FROM room_bans WHERE room_id = ? AND banned_id = ?', (room_id, uid))
        if await cur.fetchone():
            raise HTTPException(status_code=403, detail='user is banned')
        await db.execute('INSERT OR IGNORE INTO memberships (room_id, user_id, created_at) VALUES (?, ?, ?)', (room_id, uid, int(time.time())))
        await db.commit()
        return {'ok': True}


@router.post('/rooms/{room_id}/invite')
async def invite_to_room(room_id: int, request: Request, user=Depends(require_auth)):
    """Owner/admin may invite a user to a private room. Body: { invitee_id }
    Invites are recorded in `invitations` and can be accepted by the invitee.
    """
    body = await request.json()
    invitee = body.get('invitee_id')
    if not invitee:
        raise HTTPException(status_code=400, detail='invitee_id required')
    async with aiosqlite.connect(DB) as db:
        checker = _is_owner_or_admin(db, room_id, user['id'])
        if not await checker():
            raise HTTPException(status_code=403, detail='not authorized')
        # ensure room exists and is private
        cur = await db.execute('SELECT visibility FROM rooms WHERE id = ?', (room_id,))
        row = await cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail='room not found')
        if row[0] != 'private':
            raise HTTPException(status_code=400, detail='invites only for private rooms')
        # insert invitation
        await db.execute('INSERT OR IGNORE INTO invitations (room_id, inviter_id, invitee_id, created_at) VALUES (?, ?, ?, ?)', (room_id, user['id'], invitee, int(time.time())))
        await db.commit()
        return {'ok': True}


@router.get('/rooms/{room_id}/invites')
async def list_invites(room_id: int, user=Depends(require_auth)):
    """List invitations for a room (admins/owner) or for the authenticated user (invitee)."""
    async with aiosqlite.connect(DB) as db:
        # if caller is owner/admin, list invites for room
        checker = _is_owner_or_admin(db, room_id, user['id'])
        if await checker():
            cur = await db.execute('SELECT id, inviter_id, invitee_id, created_at FROM invitations WHERE room_id = ?', (room_id,))
            rows = await cur.fetchall()
            invs = [{'id': r[0], 'inviter_id': r[1], 'invitee_id': r[2], 'created_at': r[3]} for r in rows]
            return {'invites': invs}
        # otherwise list invites for this user across rooms
        cur = await db.execute('SELECT id, room_id, inviter_id, created_at FROM invitations WHERE invitee_id = ?', (user['id'],))
        rows = await cur.fetchall()
        invs = [{'id': r[0], 'room_id': r[1], 'inviter_id': r[2], 'created_at': r[3]} for r in rows]
        return {'invites': invs}


@router.post('/rooms/{room_id}/invites/{invite_id}/accept')
async def accept_invite(room_id: int, invite_id: int, user=Depends(require_auth)):
    async with aiosqlite.connect(DB) as db:
        cur = await db.execute('SELECT invitee_id FROM invitations WHERE id = ? AND room_id = ?', (invite_id, room_id))
        row = await cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail='invite not found')
        if row[0] != user['id']:
            raise HTTPException(status_code=403, detail='not the invitee')
        # add membership (but respect bans)
        cur = await db.execute('SELECT id FROM room_bans WHERE room_id = ? AND banned_id = ?', (room_id, user['id']))
        if await cur.fetchone():
            raise HTTPException(status_code=403, detail='banned from room')
        await db.execute('INSERT OR IGNORE INTO memberships (room_id, user_id, created_at) VALUES (?, ?, ?)', (room_id, user['id'], int(time.time())))
        await db.execute('DELETE FROM invitations WHERE id = ?', (invite_id,))
        await db.commit()
        return {'ok': True}


@router.post('/rooms/{room_id}/invites/{invite_id}/decline')
async def decline_invite(room_id: int, invite_id: int, user=Depends(require_auth)):
    async with aiosqlite.connect(DB) as db:
        cur = await db.execute('SELECT invitee_id FROM invitations WHERE id = ? AND room_id = ?', (invite_id, room_id))
        row = await cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail='invite not found')
        if row[0] != user['id']:
            raise HTTPException(status_code=403, detail='not the invitee')
        await db.execute('DELETE FROM invitations WHERE id = ?', (invite_id,))
        await db.commit()
        return {'ok': True}


@router.post('/rooms/{room_id}/messages')
async def post_room_message(room_id: int, request: Request, user=Depends(require_auth)):
    """Post a message to a room. Body: { text }
    - public rooms: any registered user may post unless banned
    - private rooms: only members may post
    Banned users cannot post.
    """
    body = await request.json()
    text = body.get('text')
    reply_to = body.get('reply_to')
    if text is None:
        raise HTTPException(status_code=400, detail='text required')
    # enforce UTF-8 size limit: 3 KB
    try:
        size = len(text.encode('utf-8'))
    except Exception:
        raise HTTPException(status_code=400, detail='invalid text encoding')
    if size > 3 * 1024:
        raise HTTPException(status_code=400, detail='text too long (max 3KB)')
    async with aiosqlite.connect(DB) as db:
        cur = await db.execute('SELECT visibility FROM rooms WHERE id = ?', (room_id,))
        row = await cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail='room not found')
        visibility = row[0]
        # banned check
        cur = await db.execute('SELECT id FROM room_bans WHERE room_id = ? AND banned_id = ?', (room_id, user['id']))
        if await cur.fetchone():
            raise HTTPException(status_code=403, detail='banned from room')
        if visibility == 'private':
            cur = await db.execute('SELECT id FROM memberships WHERE room_id = ? AND user_id = ?', (room_id, user['id']))
            if not await cur.fetchone():
                raise HTTPException(status_code=403, detail='private room')
        # if reply_to provided, ensure it exists and belongs to this room
        if reply_to:
            cur = await db.execute('SELECT id FROM messages WHERE id = ? AND room_id = ?', (reply_to, room_id))
            if not await cur.fetchone():
                raise HTTPException(status_code=400, detail='invalid reply_to')

        await db.execute('INSERT INTO messages (room_id, user_id, text, reply_to, created_at) VALUES (?, ?, ?, ?, ?)', (room_id, user['id'], text, reply_to, int(time.time())))
        await db.commit()
        cur = await db.execute('SELECT id, room_id, user_id, text, reply_to, created_at FROM messages WHERE rowid = last_insert_rowid()')
        r = await cur.fetchone()
        if r:
            # include edited_at if present
            msg = {'id': r[0], 'room_id': r[1], 'user_id': r[2], 'text': r[3], 'reply_to': r[4], 'created_at': r[5]}
            if len(r) > 6:
                msg['edited_at'] = r[6]
            # attach reply preview object if reply_to exists
            if msg.get('reply_to'):
                cur = await db.execute('SELECT id, user_id, text, created_at FROM messages WHERE id = ? AND room_id = ?', (msg['reply_to'], room_id))
                rr = await cur.fetchone()
                if rr:
                    msg['reply'] = {'id': rr[0], 'user_id': rr[1], 'text': rr[2], 'created_at': rr[3]}
        else:
            msg = {'room_id': room_id, 'user_id': user['id'], 'text': text}
        return {'message': msg}


@router.get('/rooms/{room_id}/messages')
async def list_room_messages(room_id: int, user=Depends(require_auth), limit: int = 50, offset: int = 0, before: int = None):
    """List messages for a room. Private rooms require membership."""
    async with aiosqlite.connect(DB) as db:
        cur = await db.execute('SELECT visibility FROM rooms WHERE id = ?', (room_id,))
        row = await cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail='room not found')
        visibility = row[0]
        # banned check
        cur = await db.execute('SELECT id FROM room_bans WHERE room_id = ? AND banned_id = ?', (room_id, user['id']))
        if await cur.fetchone():
            raise HTTPException(status_code=403, detail='banned from room')
        if visibility == 'private':
            cur = await db.execute('SELECT id FROM memberships WHERE room_id = ? AND user_id = ?', (room_id, user['id']))
            if not await cur.fetchone():
                raise HTTPException(status_code=403, detail='private room')

        # Fetch messages and their attached file metadata in a single joined query to avoid
        # an additional IN(...) lookup per request. This returns one row per message-file
        # pair (or a single row with NULL file columns if no attachment); we'll aggregate
        # in Python to build the messages list with a 'files' array.
        if before is None:
            q = '''
            SELECT m.id, m.user_id, m.text, m.reply_to, m.created_at, m.edited_at,
                   rf.id as file_id, rf.room_id as file_room_id, rf.path as file_path, rf.original_filename as file_name, rf.comment as file_comment, rf.created_at as file_created
            FROM messages m
            LEFT JOIN message_files mf ON mf.message_id = m.id
            LEFT JOIN room_files rf ON rf.id = mf.room_file_id
            WHERE m.room_id = ?
            ORDER BY m.created_at ASC
            LIMIT ? OFFSET ?
            '''
            cur = await db.execute(q, (room_id, limit, offset))
            rows = await cur.fetchall()
        else:
            q = '''
            SELECT m.id, m.user_id, m.text, m.reply_to, m.created_at, m.edited_at,
                   rf.id as file_id, rf.room_id as file_room_id, rf.path as file_path, rf.original_filename as file_name, rf.comment as file_comment, rf.created_at as file_created
            FROM messages m
            LEFT JOIN message_files mf ON mf.message_id = m.id
            LEFT JOIN room_files rf ON rf.id = mf.room_file_id
            WHERE m.room_id = ? AND m.created_at < ?
            ORDER BY m.created_at DESC
            LIMIT ? OFFSET ?
            '''
            cur = await db.execute(q, (room_id, before, limit, offset))
            rows_desc = await cur.fetchall()
            rows = list(reversed(rows_desc))

        # aggregate rows into messages preserving order
        logging.getLogger(__name__).info('list_room_messages: fetched %d rows from joined query', len(rows))
        msgs_map = {}
        order = []
        reply_ids = set()
        for r in rows:
            mid = r[0]
            uid = r[1]
            text = r[2]
            reply_to = r[3]
            created_at = r[4]
            edited_at = r[5]
            file_id = r[6]
            file_room_id = r[7]
            file_path = r[8]
            file_name = r[9]
            file_comment = r[10]
            file_created = r[11]
            if mid not in msgs_map:
                msgs_map[mid] = {'id': mid, 'user_id': uid, 'text': text, 'reply_to': reply_to, 'reply': None, 'created_at': created_at, 'files': []}
                if edited_at:
                    msgs_map[mid]['edited_at'] = edited_at
                order.append(mid)
                if reply_to:
                    reply_ids.add(reply_to)
            # append file metadata if present
            if file_id is not None:
                try:
                    fo = {'id': file_id, 'room_id': file_room_id, 'path': file_path, 'original_filename': file_name, 'comment': file_comment, 'created_at': file_created, 'url': f"/rooms/{file_room_id}/files/{file_id}"}
                    msgs_map[mid]['files'].append(fo)
                except Exception:
                    pass
        # log how many messages had files attached
        total_files_attached = sum(len(m['files']) for m in msgs_map.values())
        logging.getLogger(__name__).info('list_room_messages: attached %d total files across %d messages', total_files_attached, len(msgs_map))

        # determine if the requester is owner or admin; admins may see previews of messages
        checker = _is_owner_or_admin(db, room_id, user['id'])
        is_admin = await checker()
        # gather banned ids for this room to avoid leaking previews for banned users
        cur = await db.execute('SELECT banned_id FROM room_bans WHERE room_id = ?', (room_id,))
        banned_ids = {r[0] for r in await cur.fetchall()}

        # fetch reply preview objects for any replies referenced by the returned messages
        reply_map = {}
        if reply_ids:
            q = f"SELECT id, user_id, text, created_at FROM messages WHERE id IN ({','.join(['?']*len(reply_ids))})"
            cur = await db.execute(q, tuple(reply_ids))
            rrows = await cur.fetchall()
            for r in rrows:
                mid_r, muid, mtext, mcreated = r
                if not is_admin and muid in banned_ids:
                    continue
                reply_map[mid_r] = {'id': mid_r, 'user_id': muid, 'text': mtext, 'created_at': mcreated}

        msgs = []
        for mid in order:
            m = msgs_map.get(mid)
            if m:
                # attach resolved reply object if any
                if m.get('reply_to'):
                    m['reply'] = reply_map.get(m['reply_to'])
                msgs.append(m)

        # Resolve a human-friendly display name for each referenced user id (messages + replies).
        try:
            user_ids = set()
            for m in msgs:
                if m.get('user_id'):
                    user_ids.add(m['user_id'])
                if m.get('reply') and m['reply'].get('user_id'):
                    user_ids.add(m['reply']['user_id'])
            if user_ids:
                placeholders = ','.join(['?'] * len(user_ids))
                q = f"SELECT id, username, email FROM users WHERE id IN ({placeholders})"
                cur = await db.execute(q, tuple(user_ids))
                urows = await cur.fetchall()
                name_by_id = {}
                for ur in urows:
                    try:
                        uid = ur[0]
                        uname = ur[1] or ur[2] or (f'user{uid}')
                        name_by_id[uid] = uname
                    except Exception:
                        pass
                for m in msgs:
                    try:
                        if m.get('user_id') and m['user_id'] in name_by_id:
                            m['display_name'] = name_by_id[m['user_id']]
                        if m.get('reply') and m['reply'].get('user_id') and m['reply']['user_id'] in name_by_id:
                            m['reply']['display_name'] = name_by_id[m['reply']['user_id']]
                    except Exception:
                        pass
        except Exception:
            pass

        # Fallback: ensure any files referenced by these messages are attached.
        # Some SQLite builds or driver behaviors can produce surprises with JOINs;
        # do a single IN(...) lookup to be robust (still a single query).
        try:
            msg_ids = [m['id'] for m in msgs]
            if msg_ids:
                q = f"SELECT mf.message_id, rf.id, rf.room_id, rf.path, rf.original_filename, rf.comment, rf.created_at FROM message_files mf JOIN room_files rf ON rf.id = mf.room_file_id WHERE mf.message_id IN ({','.join(['?']*len(msg_ids))})"
                cur = await db.execute(q, tuple(msg_ids))
                file_rows = await cur.fetchall()
                files_by_msg = {}
                for fr in file_rows:
                    mid_fk, rf_id, rf_room_id, rf_path, rf_name, rf_comment, rf_created = fr
                    file_obj = {'id': rf_id, 'room_id': rf_room_id, 'path': rf_path, 'original_filename': rf_name, 'comment': rf_comment, 'created_at': rf_created, 'url': f"/rooms/{rf_room_id}/files/{rf_id}"}
                    files_by_msg.setdefault(mid_fk, []).append(file_obj)
                for m in msgs:
                    if m['id'] in files_by_msg:
                        m['files'] = files_by_msg[m['id']]
        except Exception:
            # non-fatal: if attachment lookup fails, return messages without files
            pass

        # mark as read: update memberships.last_read_at for this user/room to now
        try:
            await db.execute('UPDATE memberships SET last_read_at = ? WHERE room_id = ? AND user_id = ?', (int(time.time()), room_id, user['id']))
            await db.commit()
        except Exception:
            pass

        # DEBUG: print rows and messages to server stdout for diagnosis (temporary)
        try:
            print('DEBUG JOIN_ROWS_COUNT:', len(rows))
            # print per-message files count
            for m in msgs:
                print('DEBUG MSG:', m.get('id'), 'files_count=', len(m.get('files', [])))
        except Exception:
            pass

        return {'messages': msgs}


@router.post('/rooms/{room_id}/messages/{message_id}/edit')
async def edit_room_message(room_id: int, message_id: int, request: Request, user=Depends(require_auth)):
    """Allow the message author to edit their message. Body: { text }
    Returns the updated message.
    """
    body = await request.json()
    text = body.get('text')
    if text is None:
        raise HTTPException(status_code=400, detail='text required')
    try:
        size = len(text.encode('utf-8'))
    except Exception:
        raise HTTPException(status_code=400, detail='invalid text encoding')
    if size > 3 * 1024:
        raise HTTPException(status_code=400, detail='text too long (max 3KB)')
    async with aiosqlite.connect(DB) as db:
        # ensure message exists and belongs to room
        cur = await db.execute('SELECT user_id FROM messages WHERE id = ? AND room_id = ?', (message_id, room_id))
        row = await cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail='message not found')
        if row[0] != user['id']:
            raise HTTPException(status_code=403, detail='not message author')
        await db.execute('UPDATE messages SET text = ?, edited_at = ? WHERE id = ? AND room_id = ?', (text, int(time.time()), message_id, room_id))
        await db.commit()
        cur = await db.execute('SELECT id, room_id, user_id, text, reply_to, created_at, edited_at FROM messages WHERE id = ? AND room_id = ?', (message_id, room_id))
        r = await cur.fetchone()
        msg = {'id': r[0], 'room_id': r[1], 'user_id': r[2], 'text': r[3], 'reply_to': r[4], 'created_at': r[5], 'edited_at': r[6]}
        return {'message': msg}
