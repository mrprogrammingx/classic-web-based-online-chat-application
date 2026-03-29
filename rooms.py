from routers.rooms import router

__all__ = ['router']
from fastapi import APIRouter, Request, HTTPException, Depends
import aiosqlite
import time
import db as db_mod
from core.utils import require_auth
DB = db_mod.DB

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
    async with aiosqlite.connect(db_mod.DB) as db:
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
    async with aiosqlite.connect(db_mod.DB) as db:
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
    async with aiosqlite.connect(db_mod.DB) as db:
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
        from routers.rooms import router

        __all__ = ['router']
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
        # an additional IN(...) lookup per request. Aggregate rows into messages with a 'files' array.
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
            if file_id is not None:
                try:
                    fo = {'id': file_id, 'room_id': file_room_id, 'path': file_path, 'original_filename': file_name, 'comment': file_comment, 'created_at': file_created, 'url': f"/rooms/{file_room_id}/files/{file_id}"}
                    msgs_map[mid]['files'].append(fo)
                except Exception:
                    pass

        checker = _is_owner_or_admin(db, room_id, user['id'])
        is_admin = await checker()
        cur = await db.execute('SELECT banned_id FROM room_bans WHERE room_id = ?', (room_id,))
        banned_ids = {r[0] for r in await cur.fetchall()}

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
                if m.get('reply_to'):
                    m['reply'] = reply_map.get(m['reply_to'])
                msgs.append(m)

        # Resolve display_name for message authors and reply authors
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

        # Attach any files uploaded for these messages. We look up message_files -> room_files
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
