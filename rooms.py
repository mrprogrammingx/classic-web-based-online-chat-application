from fastapi import APIRouter, Request, HTTPException, Depends
import aiosqlite
import time
from db import DB
from utils import require_auth

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
async def list_rooms(q: str = None, limit: int = 50, offset: int = 0):
    """List public rooms. Supports simple search via `q` (substring match on name or description).

    Returns each room with a `member_count` field.
    """
    async with aiosqlite.connect(DB) as db:
        params = []
        where = "WHERE visibility = 'public'"
        if q:
            where += " AND (name LIKE ? OR description LIKE ?)"
            pattern = f"%{q}%"
            params.extend([pattern, pattern])
        # limit/offset for simple pagination
        params.extend([limit, offset])
        # join memberships to compute member counts
        sql = f"""
        SELECT r.id, r.owner_id, r.name, r.description, r.visibility, r.created_at,
               COUNT(m.id) as member_count
        FROM rooms r
        LEFT JOIN memberships m ON m.room_id = r.id
        {where}
        GROUP BY r.id
        ORDER BY r.created_at DESC
        LIMIT ? OFFSET ?
        """
        cur = await db.execute(sql, params)
        rows = await cur.fetchall()
        rooms = [
            {
                'id': r[0],
                'owner_id': r[1],
                'name': r[2],
                'description': r[3],
                'visibility': r[4],
                'created_at': r[5],
                'member_count': r[6],
            }
            for r in rows
        ]
        return {'rooms': rooms}


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
        # list admins and members
        cur = await db.execute('SELECT user_id FROM room_admins WHERE room_id = ?', (room_id,))
        admins = [r[0] for r in await cur.fetchall()]
        cur = await db.execute('SELECT user_id FROM memberships WHERE room_id = ?', (room_id,))
        members = [r[0] for r in await cur.fetchall()]
        cur = await db.execute('SELECT banned_id FROM room_bans WHERE room_id = ?', (room_id,))
        bans = [r[0] for r in await cur.fetchall()]
        room.update({'admins': admins, 'members': members, 'bans': bans})
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
        await db.execute('INSERT OR IGNORE INTO memberships (room_id, user_id, created_at) VALUES (?, ?, ?)', (room_id, user['id'], int(time.time())))
        await db.commit()
        return {'ok': True}


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
        if visibility == 'private':
            cur = await db.execute('SELECT id FROM memberships WHERE room_id = ? AND user_id = ?', (room_id, user['id']))
            if not await cur.fetchone():
                raise HTTPException(status_code=403, detail='private room')
        cur = await db.execute('SELECT id, path, created_at FROM room_files WHERE room_id = ?', (room_id,))
        rows = await cur.fetchall()
        files = [{'id': r[0], 'path': r[1], 'created_at': r[2]} for r in rows]
        return {'files': files}


from fastapi.responses import FileResponse


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
        # check room visibility/membership
        cur = await db.execute('SELECT visibility FROM rooms WHERE id = ?', (room_id,))
        r2 = await cur.fetchone()
        if not r2:
            raise HTTPException(status_code=404, detail='room not found')
        visibility = r2[0]
        if visibility == 'private':
            cur = await db.execute('SELECT id FROM memberships WHERE room_id = ? AND user_id = ?', (room_id, user['id']))
            if not await cur.fetchone():
                raise HTTPException(status_code=403, detail='private room')
        # resolve path
        import os

        p = path
        if not os.path.isabs(p):
            p = os.path.join('uploads', p)
        if not os.path.exists(p):
            raise HTTPException(status_code=404, detail='file not found on disk')
        return FileResponse(p)


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
        else:
            msg = {'room_id': room_id, 'user_id': user['id'], 'text': text}
        return {'message': msg}


@router.get('/rooms/{room_id}/messages')
async def list_room_messages(room_id: int, user=Depends(require_auth), limit: int = 50, offset: int = 0):
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
        cur = await db.execute('SELECT id, user_id, text, reply_to, created_at, edited_at FROM messages WHERE room_id = ? ORDER BY created_at ASC LIMIT ? OFFSET ?', (room_id, limit, offset))
        rows = await cur.fetchall()
        msgs = []
        reply_ids = {r[3] for r in rows if r[3]}
        # determine if the requester is owner or admin; admins may see previews of messages
        checker = _is_owner_or_admin(db, room_id, user['id'])
        is_admin = await checker()
        # gather banned ids for this room to avoid leaking previews for banned users
        cur = await db.execute('SELECT banned_id FROM room_bans WHERE room_id = ?', (room_id,))
        banned_ids = {r[0] for r in await cur.fetchall()}

        reply_map = {}
        if reply_ids:
            q = f"SELECT id, user_id, text, created_at FROM messages WHERE id IN ({','.join(['?']*len(reply_ids))})"
            cur = await db.execute(q, tuple(reply_ids))
            rrows = await cur.fetchall()
            # only include reply previews if the referenced message's author is not banned,
            # or the requester is an admin/owner (admins can see previews for moderation)
            for r in rrows:
                mid, muid, mtext, mcreated = r
                if not is_admin and muid in banned_ids:
                    # skip including preview to avoid leaking banned user's content
                    continue
                reply_map[mid] = {'id': mid, 'user_id': muid, 'text': mtext, 'created_at': mcreated}
        for r in rows:
            mid, uid, text, reply_to, created_at, edited_at = r
            reply_obj = reply_map.get(reply_to)
            entry = {'id': mid, 'user_id': uid, 'text': text, 'reply_to': reply_to, 'reply': reply_obj, 'created_at': created_at}
            if edited_at:
                entry['edited_at'] = edited_at
            msgs.append(entry)
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
