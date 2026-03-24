from fastapi import APIRouter, Request, Depends, HTTPException
import aiosqlite
from db import DB
from utils import require_auth
import time

router = APIRouter()


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
    return {'message': msg}


async def _send_private_message(from_id: int, to_id: int, text: str, reply_to: int | None):
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
async def dialog_history(other_id: int, user=Depends(require_auth), limit: int = 50, offset: int = 0):
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
        cur = await db.execute(
            'SELECT id, from_id, to_id, text, reply_to, created_at, edited_at, delivered_at FROM private_messages WHERE (from_id = ? AND to_id = ?) OR (from_id = ? AND to_id = ?) ORDER BY created_at ASC LIMIT ? OFFSET ?',
            (user['id'], other_id, other_id, user['id'], limit, offset)
        )
        rows = await cur.fetchall()
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
        # list files where (from=user and to=other) OR (from=other and to=user)
        cur = await db.execute('SELECT id, message_id, from_id, to_id, path, created_at FROM private_message_files WHERE (from_id = ? AND to_id = ?) OR (from_id = ? AND to_id = ?) ORDER BY created_at ASC', (user['id'], other_id, other_id, user['id']))
        rows = await cur.fetchall()
        files = [{'id': r[0], 'message_id': r[1], 'from_id': r[2], 'to_id': r[3], 'path': r[4], 'created_at': r[5]} for r in rows]
        return {'files': files}
