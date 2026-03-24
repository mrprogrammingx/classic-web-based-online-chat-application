from fastapi import APIRouter, Request, Depends, HTTPException
import aiosqlite
from db import DB
from utils import require_auth
import time
from fastapi import UploadFile, File, Form
from fastapi.responses import FileResponse
import os
import uuid
from typing import Optional

router = APIRouter()

# Use TEST_UPLOAD_DIR when running tests (set in .env.test), otherwise default to 'uploads'
UPLOADS_DIR = os.path.join(os.getcwd(), os.getenv('TEST_UPLOAD_DIR', 'uploads'))
os.makedirs(UPLOADS_DIR, exist_ok=True)


@router.post('/dialogs/{other_id}/messages')
async def send_dialog_message(other_id: int, request: Request, user=Depends(require_auth)):
    """Send a personal (dialog) message to another user. Path param other_id is the other participant.

    Body: { text }
    Returns the created message in the same shape as room messages: { user_id, text, created_at }
    """
    body = await request.json()
    text = body.get('text')
    reply_to = body.get('reply_to')
    if text is None:
        raise HTTPException(status_code=400, detail='text required')
    try:
        size = len(text.encode('utf-8'))
    except Exception:
        raise HTTPException(status_code=400, detail='invalid text encoding')
    if size > 3 * 1024:
        raise HTTPException(status_code=400, detail='text too long (max 3KB)')
    if other_id == user['id']:
        raise HTTPException(status_code=400, detail="can't message yourself")

    msg = await _send_private_message(user['id'], other_id, text, reply_to)
    # attach a reply preview if applicable
    if msg.get('reply_to'):
        async with aiosqlite.connect(DB) as db:
            cur = await db.execute('SELECT id, from_id, to_id, text, created_at FROM private_messages WHERE id = ?', (msg['reply_to'],))
            r = await cur.fetchone()
            if r:
                msg['reply'] = {'id': r[0], 'from_id': r[1], 'to_id': r[2], 'text': r[3], 'created_at': r[4]}
    return {'message': msg}


async def _send_private_message(from_id: int, to_id: int, text: str, reply_to: Optional[int]):
    """Internal helper to send a private message and return the created message dict.

    Raises HTTPException for permission/validation errors.
    """
    async with aiosqlite.connect(DB) as db:
        # ban check (either direction) using global bans table
        cur = await db.execute(
            'SELECT 1 FROM bans WHERE (banner_id = ? AND banned_id = ?) OR (banner_id = ? AND banned_id = ?)',
            (from_id, to_id, to_id, from_id)
        )
        if await cur.fetchone():
            raise HTTPException(status_code=403, detail='ban exists between users')

        # require mutual friendship (app policy) - reuse existing friends table
        cur = await db.execute('SELECT 1 FROM friends WHERE user_id = ? AND friend_id = ?', (from_id, to_id))
        a = await cur.fetchone()
        cur = await db.execute('SELECT 1 FROM friends WHERE user_id = ? AND friend_id = ?', (to_id, from_id))
        b = await cur.fetchone()
        if not (a and b):
            raise HTTPException(status_code=403, detail='users not friends')

        # validate reply_to if provided (must exist and be between the two participants)
        if reply_to:
            cur = await db.execute('SELECT id, from_id, to_id FROM private_messages WHERE id = ?', (reply_to,))
            prow = await cur.fetchone()
            if not prow:
                raise HTTPException(status_code=400, detail='invalid reply_to')
            # ensure reply is within the same dialog
            if not ((prow[1] == from_id and prow[2] == to_id) or (prow[1] == to_id and prow[2] == from_id)):
                raise HTTPException(status_code=400, detail='reply_to not in dialog')

        # insert message and return created row in same shape as room message
        await db.execute('INSERT INTO private_messages (from_id, to_id, text, reply_to, created_at) VALUES (?, ?, ?, ?, ?)',
                         (from_id, to_id, text, reply_to, int(time.time())))
        await db.commit()
        cur = await db.execute('SELECT id, from_id, to_id, text, reply_to, created_at FROM private_messages WHERE rowid = last_insert_rowid()')
        r = await cur.fetchone()
        msg = {'id': r[0], 'user_id': r[1], 'to_id': r[2], 'text': r[3], 'reply_to': r[4], 'created_at': r[5]} if r else {'user_id': from_id, 'to_id': to_id, 'text': text}
        return msg


@router.post('/messages/send')
async def send_message_compat(request: Request, user=Depends(require_auth)):
    """Compatibility endpoint used by older clients/tests. Body: { to_id, text, reply_to? }"""
    body = await request.json()
    to_id = body.get('to_id')
    text = body.get('text')
    reply_to = body.get('reply_to')
    if not to_id or text is None:
        raise HTTPException(status_code=400, detail='to_id and text required')
    msg = await _send_private_message(user['id'], int(to_id), text, reply_to)
    return {'message': msg}


@router.get('/dialogs/{other_id}/messages')
async def dialog_history(other_id: int, user=Depends(require_auth), limit: int = 50, offset: int = 0, before: int = None):
    """Return dialog (personal) message history between authenticated user and other_id.

    Response: { read_only: bool, messages: [ { user_id, text, created_at } ] }
    """
    async with aiosqlite.connect(DB) as db:
        # check if ban exists either direction
        cur = await db.execute(
            'SELECT 1 FROM bans WHERE (banner_id = ? AND banned_id = ?) OR (banner_id = ? AND banned_id = ?)',
            (user['id'], other_id, other_id, user['id'])
        )
        banned = bool(await cur.fetchone())
        # fetch messages and normalize shape to match room messages
        if before is None:
            cur = await db.execute(
                'SELECT id, from_id, to_id, text, reply_to, created_at, edited_at, delivered_at FROM private_messages WHERE (from_id = ? AND to_id = ?) OR (from_id = ? AND to_id = ?) ORDER BY created_at ASC LIMIT ? OFFSET ?',
                (user['id'], other_id, other_id, user['id'], limit, offset)
            )
            rows = await cur.fetchall()
        else:
            cur = await db.execute(
                'SELECT id, from_id, to_id, text, reply_to, created_at, edited_at, delivered_at FROM private_messages WHERE ((from_id = ? AND to_id = ?) OR (from_id = ? AND to_id = ?)) AND created_at < ? ORDER BY created_at DESC LIMIT ? OFFSET ?',
                (user['id'], other_id, other_id, user['id'], before, limit, offset)
            )
            rows_desc = await cur.fetchall()
            # normalize to ascending order
            rows = list(reversed(rows_desc))
        msgs = []
        reply_ids = {r[4] for r in rows if r[4]}
        reply_map = {}
        if reply_ids:
            q = f"SELECT id, from_id, to_id, text, created_at FROM private_messages WHERE id IN ({','.join(['?']*len(reply_ids))})"
            cur = await db.execute(q, tuple(reply_ids))
            rrows = await cur.fetchall()
            reply_map = {r[0]: {'id': r[0], 'from_id': r[1], 'to_id': r[2], 'text': r[3], 'created_at': r[4]} for r in rrows}
        # mark delivered messages as delivered when the recipient fetches the dialog (simulate delivery on open)
        to_mark = [r[0] for r in rows if r[2] == user['id'] and r[7] is None]
        now_ts = int(time.time())
        if to_mark:
            q = f"UPDATE private_messages SET delivered_at = ? WHERE id IN ({','.join(['?']*len(to_mark))})"
            await db.execute(q, tuple([now_ts] + to_mark))
            await db.commit()
            to_mark_set = set(to_mark)
        for r in rows:
            mid, uid, toid, text, reply_to, created_at, edited_at, delivered_at = r
            # if we just marked this message as delivered, reflect it in the response
            if 'to_mark_set' in locals() and mid in to_mark_set:
                delivered_at = now_ts
            reply_obj = reply_map.get(reply_to)
            entry = {'id': mid, 'user_id': uid, 'to_id': toid, 'text': text, 'reply_to': reply_to, 'reply': reply_obj, 'created_at': created_at}
            if edited_at:
                entry['edited_at'] = edited_at
            if delivered_at:
                entry['delivered_at'] = delivered_at
            msgs.append(entry)
        # Attach files to messages: query private_message_files where message_id in message ids
        msg_ids = [m['id'] for m in msgs]
        if msg_ids:
            q = f"SELECT id, message_id, from_id, to_id, path, original_filename, comment, created_at FROM private_message_files WHERE message_id IN ({','.join(['?']*len(msg_ids))})"
            cur = await db.execute(q, tuple(msg_ids))
            frows = await cur.fetchall()
            files_by_msg = {}
            for fr in frows:
                fid, mid_ref, fr_from, fr_to, fpath, forig, fcomm, fcreated = fr
                url = f"/dialogs/{other_id}/files/{fid}"
                meta = {'id': fid, 'message_id': mid_ref, 'from_id': fr_from, 'to_id': fr_to, 'path': fpath, 'original_filename': forig, 'comment': fcomm, 'created_at': fcreated, 'url': url}
                files_by_msg.setdefault(mid_ref, []).append(meta)
            for m in msgs:
                if m['id'] in files_by_msg:
                    m['files'] = files_by_msg[m['id']]
        # mark dialog as read for this user: update or insert into dialog_reads
        try:
            await db.execute('INSERT OR REPLACE INTO dialog_reads (user_id, other_id, last_read_at) VALUES (?, ?, ?)', (user['id'], other_id, int(time.time())))
            await db.commit()
        except Exception:
            pass

        return {'read_only': banned, 'messages': msgs}


@router.get('/messages/history')
async def messages_history(with_id: int, user=Depends(require_auth), limit: int = 50, offset: int = 0):
    # delegate to dialog_history for compatibility
    return await dialog_history(with_id, user, limit, offset)



@router.post('/dialogs/{other_id}/messages/{message_id}/edit')
async def edit_dialog_message(other_id: int, message_id: int, request: Request, user=Depends(require_auth)):
    """Allow the author of a dialog message to edit it."""
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
        # ensure message exists
        cur = await db.execute('SELECT from_id, to_id FROM private_messages WHERE id = ?', (message_id,))
        row = await cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail='message not found')
        if row[0] != user['id']:
            raise HTTPException(status_code=403, detail='not message author')
        # ensure message belongs to this dialog
        if not ((row[0] == user['id'] and row[1] == other_id) or (row[0] == other_id and row[1] == user['id'])):
            raise HTTPException(status_code=400, detail='message not in dialog')
        await db.execute('UPDATE private_messages SET text = ?, edited_at = ? WHERE id = ?', (text, int(time.time()), message_id))
        await db.commit()
        cur = await db.execute('SELECT id, from_id, to_id, text, reply_to, created_at, edited_at FROM private_messages WHERE id = ?', (message_id,))
        r = await cur.fetchone()
        msg = {'id': r[0], 'user_id': r[1], 'to_id': r[2], 'text': r[3], 'reply_to': r[4], 'created_at': r[5], 'edited_at': r[6]}
        return {'message': msg}


@router.delete('/dialogs/{other_id}/messages/{message_id}')
async def delete_dialog_message(other_id: int, message_id: int, user=Depends(require_auth)):
    """Allow the author of a dialog message to delete it."""
    async with aiosqlite.connect(DB) as db:
        cur = await db.execute('SELECT from_id, to_id FROM private_messages WHERE id = ?', (message_id,))
        row = await cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail='message not found')
        # verify message is in this dialog
        if not ((row[0] == user['id'] and row[1] == other_id) or (row[0] == other_id and row[1] == user['id'])):
            raise HTTPException(status_code=403, detail='not in dialog')
        if row[0] != user['id']:
            raise HTTPException(status_code=403, detail='not message author')
        await db.execute('DELETE FROM private_messages WHERE id = ?', (message_id,))
        await db.commit()
        return {'ok': True}


@router.get('/dialogs/{other_id}/files')
async def dialog_files(other_id: int, user=Depends(require_auth)):
    """List attachments exchanged in a dialog between the authenticated user and other_id.

    Returns: { files: [ { id, path, created_at, from_id, to_id } ] }
    """
    async with aiosqlite.connect(DB) as db:
        # ensure participant ids
        cur = await db.execute('SELECT 1 FROM users WHERE id = ?', (other_id,))
        if not await cur.fetchone():
            raise HTTPException(status_code=404, detail='user not found')
        # ensure access: no bans and mutual friendship
        cur = await db.execute(
            'SELECT 1 FROM bans WHERE (banner_id = ? AND banned_id = ?) OR (banner_id = ? AND banned_id = ?)',
            (user['id'], other_id, other_id, user['id'])
        )
        if await cur.fetchone():
            raise HTTPException(status_code=403, detail='read_only')
        cur = await db.execute('SELECT 1 FROM friends WHERE user_id = ? AND friend_id = ?', (user['id'], other_id))
        a = await cur.fetchone()
        cur = await db.execute('SELECT 1 FROM friends WHERE user_id = ? AND friend_id = ?', (other_id, user['id']))
        b = await cur.fetchone()
        if not (a and b):
            raise HTTPException(status_code=403, detail='not authorized')
        # list files where (from=user and to=other) OR (from=other and to=user)
        cur = await db.execute('SELECT id, message_id, from_id, to_id, path, original_filename, comment, created_at FROM private_message_files WHERE (from_id = ? AND to_id = ?) OR (from_id = ? AND to_id = ?) ORDER BY created_at ASC', (user['id'], other_id, other_id, user['id']))
        rows = await cur.fetchall()
        files = [{'id': r[0], 'message_id': r[1], 'from_id': r[2], 'to_id': r[3], 'path': r[4], 'original_filename': r[5], 'comment': r[6], 'created_at': r[7]} for r in rows]
        return {'files': files}



@router.get('/dialogs/{other_id}/files/{file_id}')
async def get_dialog_file(other_id: int, file_id: int, user=Depends(require_auth)):
    """Serve a file attached to a dialog if the requester is a participant."""
    async with aiosqlite.connect(DB) as db:
        cur = await db.execute('SELECT path, from_id, to_id FROM private_message_files WHERE id = ?', (file_id,))
        row = await cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail='file not found')
        path, from_id, to_id = row
        # ensure requester is one of the participants
        if user['id'] not in (from_id, to_id):
            raise HTTPException(status_code=403, detail='not authorized')
        # ensure current access: no mutual ban and mutual friendship
        other = from_id if user['id'] != from_id else to_id
        cur = await db.execute(
            'SELECT 1 FROM bans WHERE (banner_id = ? AND banned_id = ?) OR (banner_id = ? AND banned_id = ?)',
            (user['id'], other, other, user['id'])
        )
        if await cur.fetchone():
            raise HTTPException(status_code=403, detail='not authorized')
        # mutual friendship check
        cur = await db.execute('SELECT 1 FROM friends WHERE user_id = ? AND friend_id = ?', (user['id'], other))
        a = await cur.fetchone()
        cur = await db.execute('SELECT 1 FROM friends WHERE user_id = ? AND friend_id = ?', (other, user['id']))
        b = await cur.fetchone()
        if not (a and b):
            raise HTTPException(status_code=403, detail='not authorized')
        # resolve path: prefer UPLOADS_DIR but fall back to legacy 'uploads'
        if os.path.isabs(path):
            fpath = path
        else:
            fpath = os.path.join(UPLOADS_DIR, path)
            if not os.path.exists(fpath):
                legacy = os.path.join(os.getcwd(), 'uploads', path)
                if os.path.exists(legacy):
                    fpath = legacy
        if not os.path.exists(fpath):
            raise HTTPException(status_code=404, detail='file not found on disk')
        return FileResponse(fpath)


@router.post('/dialogs/{other_id}/files')
async def upload_dialog_file(other_id: int, file: UploadFile = File(...), comment: Optional[str] = Form(None), message_id: Optional[int] = Form(None), user=Depends(require_auth)):
    """Upload an attachment for a dialog message. Records a private_message_files row. Returns file metadata."""
    if other_id == user['id']:
        raise HTTPException(status_code=400, detail="can't attach to yourself")
    async with aiosqlite.connect(DB) as db:
        # ban check and friendship check similar to sending messages
        cur = await db.execute('SELECT 1 FROM bans WHERE (banner_id = ? AND banned_id = ?) OR (banner_id = ? AND banned_id = ?)', (user['id'], other_id, other_id, user['id']))
        if await cur.fetchone():
            raise HTTPException(status_code=403, detail='ban exists between users')
        cur = await db.execute('SELECT 1 FROM friends WHERE user_id = ? AND friend_id = ?', (user['id'], other_id))
        a = await cur.fetchone()
        cur = await db.execute('SELECT 1 FROM friends WHERE user_id = ? AND friend_id = ?', (other_id, user['id']))
        b = await cur.fetchone()
        if not (a and b):
            raise HTTPException(status_code=403, detail='users not friends')
        uploads_dir = UPLOADS_DIR
        os.makedirs(uploads_dir, exist_ok=True)
        safe_name = f"{int(time.time())}_{uuid.uuid4().hex}_{file.filename}"
        dest_path = os.path.join(uploads_dir, safe_name)
        contents = await file.read()
        with open(dest_path, 'wb') as fh:
            fh.write(contents)
        # insert record; message_id can be null until associated with a message
        await db.execute('INSERT INTO private_message_files (message_id, from_id, to_id, path, original_filename, comment, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)', (message_id, user['id'], other_id, safe_name, file.filename, comment, int(time.time())))
        await db.commit()
        cur = await db.execute('SELECT id, message_id, from_id, to_id, path, original_filename, comment, created_at FROM private_message_files WHERE rowid = last_insert_rowid()')
        r = await cur.fetchone()
        fid = r[0]
        return {'file': {'id': fid, 'message_id': r[1], 'from_id': r[2], 'to_id': r[3], 'path': r[4], 'original_filename': r[5], 'comment': r[6], 'created_at': r[7], 'url': f"/dialogs/{other_id}/files/{fid}"}}


@router.post('/dialogs/{other_id}/messages_with_file')
async def send_dialog_message_with_file(other_id: int, file: UploadFile = File(None), text: Optional[str] = Form(None), reply_to: Optional[int] = Form(None), comment: Optional[str] = Form(None), user=Depends(require_auth)):
    """Atomic endpoint to create a dialog message and attach a file in one request.

    Accepts multipart/form-data with optional `text`, optional `file`, optional `reply_to` and optional `comment`.
    Returns { message: {...}, file?: { ... } }
    """
    if other_id == user['id']:
        raise HTTPException(status_code=400, detail="can't message yourself")
    # enforce text size limit (same rule as send_dialog_message)
    if text is not None:
        try:
            size = len(text.encode('utf-8'))
        except Exception:
            raise HTTPException(status_code=400, detail='invalid text encoding')
        if size > 3 * 1024:
            raise HTTPException(status_code=400, detail='text too long (max 3KB)')
    # create message first (validations reused)
    msg = await _send_private_message(user['id'], other_id, text or '', reply_to)
    # attach reply preview if applicable
    if msg.get('reply_to'):
        async with aiosqlite.connect(DB) as db:
            cur = await db.execute('SELECT id, from_id, to_id, text, created_at FROM private_messages WHERE id = ?', (msg['reply_to'],))
            r = await cur.fetchone()
            if r:
                msg['reply'] = {'id': r[0], 'from_id': r[1], 'to_id': r[2], 'text': r[3], 'created_at': r[4]}
    file_meta = None
    if file:
        # reuse upload logic but associate with message id
        uploads_dir = UPLOADS_DIR
        os.makedirs(uploads_dir, exist_ok=True)
        safe_name = f"{int(time.time())}_{uuid.uuid4().hex}_{file.filename}"
        dest_path = os.path.join(uploads_dir, safe_name)
        contents = await file.read()
        with open(dest_path, 'wb') as fh:
            fh.write(contents)
        async with aiosqlite.connect(DB) as db:
            await db.execute('INSERT INTO private_message_files (message_id, from_id, to_id, path, original_filename, comment, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)', (msg['id'], user['id'], other_id, safe_name, file.filename, comment, int(time.time())))
            await db.commit()
            cur = await db.execute('SELECT id, message_id, from_id, to_id, path, original_filename, comment, created_at FROM private_message_files WHERE rowid = last_insert_rowid()')
            r = await cur.fetchone()
            fid = r[0]
            file_meta = {'id': fid, 'message_id': r[1], 'from_id': r[2], 'to_id': r[3], 'path': r[4], 'original_filename': r[5], 'comment': r[6], 'created_at': r[7], 'url': f"/dialogs/{other_id}/files/{fid}"}
    return {'message': msg, 'file': file_meta}


@router.post('/dialogs/{other_id}/files/paste')
async def paste_dialog_file(other_id: int, request: Request, user=Depends(require_auth)):
    """Accept pasted file data (data URL or raw base64) in JSON and store as a dialog attachment.

    Body: { filename: str, data: str } where data may be a data URL (data:<mimetype>;base64,...) or raw base64.
    Returns same shape as upload endpoint.
    """
    body = await request.json()
    filename = body.get('filename')
    data = body.get('data')
    if not filename or not data:
        raise HTTPException(status_code=400, detail='filename and data required')
    # Normalize data URL or raw base64
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

    # reuse same permission checks as upload_dialog_file
    if other_id == user['id']:
        raise HTTPException(status_code=400, detail="can't attach to yourself")
    async with aiosqlite.connect(DB) as db:
        cur = await db.execute('SELECT 1 FROM bans WHERE (banner_id = ? AND banned_id = ?) OR (banner_id = ? AND banned_id = ?)', (user['id'], other_id, other_id, user['id']))
        if await cur.fetchone():
            raise HTTPException(status_code=403, detail='ban exists between users')
        cur = await db.execute('SELECT 1 FROM friends WHERE user_id = ? AND friend_id = ?', (user['id'], other_id))
        a = await cur.fetchone()
        cur = await db.execute('SELECT 1 FROM friends WHERE user_id = ? AND friend_id = ?', (other_id, user['id']))
        b = await cur.fetchone()
        if not (a and b):
            raise HTTPException(status_code=403, detail='users not friends')
        uploads_dir = UPLOADS_DIR
        os.makedirs(uploads_dir, exist_ok=True)
        safe_name = f"{int(time.time())}_{uuid.uuid4().hex}_{filename}"
        dest_path = os.path.join(uploads_dir, safe_name)
        with open(dest_path, 'wb') as fh:
            fh.write(raw)
        # optional comment passed in JSON
        comment = body.get('comment')
        message_id = body.get('message_id')
        await db.execute('INSERT INTO private_message_files (message_id, from_id, to_id, path, original_filename, comment, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)', (message_id, user['id'], other_id, safe_name, filename, comment, int(time.time())))
        await db.commit()
        cur = await db.execute('SELECT id, message_id, from_id, to_id, path, original_filename, comment, created_at FROM private_message_files WHERE rowid = last_insert_rowid()')
        r = await cur.fetchone()
        fid = r[0]
        return {'file': {'id': fid, 'message_id': r[1], 'from_id': r[2], 'to_id': r[3], 'path': r[4], 'original_filename': r[5], 'comment': r[6], 'created_at': r[7], 'url': f"/dialogs/{other_id}/files/{fid}"}}
