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
    if not text:
        raise HTTPException(status_code=400, detail='text required')
    if other_id == user['id']:
        raise HTTPException(status_code=400, detail="can't message yourself")

    async with aiosqlite.connect(DB) as db:
        # ban check (either direction) using global bans table
        cur = await db.execute(
            'SELECT 1 FROM bans WHERE (banner_id = ? AND banned_id = ?) OR (banner_id = ? AND banned_id = ?)',
            (user['id'], other_id, other_id, user['id'])
        )
        if await cur.fetchone():
            raise HTTPException(status_code=403, detail='ban exists between users')

        # require mutual friendship (app policy) - reuse existing friends table
        cur = await db.execute('SELECT 1 FROM friends WHERE user_id = ? AND friend_id = ?', (user['id'], other_id))
        a = await cur.fetchone()
        cur = await db.execute('SELECT 1 FROM friends WHERE user_id = ? AND friend_id = ?', (other_id, user['id']))
        b = await cur.fetchone()
        if not (a and b):
            raise HTTPException(status_code=403, detail='users not friends')

        # insert message and return created row in same shape as room message
        await db.execute('INSERT INTO private_messages (from_id, to_id, text, created_at) VALUES (?, ?, ?, ?)',
                         (user['id'], other_id, text, int(time.time())))
        await db.commit()
        cur = await db.execute('SELECT id, from_id, to_id, text, created_at FROM private_messages WHERE rowid = last_insert_rowid()')
        r = await cur.fetchone()
        msg = {'id': r[0], 'user_id': r[1], 'to_id': r[2], 'text': r[3], 'created_at': r[4]} if r else {'user_id': user['id'], 'to_id': other_id, 'text': text}
        return {'message': msg}


@router.get('/dialogs/{other_id}/messages')
async def dialog_history(other_id: int, user=Depends(require_auth)):
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
            'SELECT from_id, to_id, text, created_at FROM private_messages WHERE (from_id = ? AND to_id = ?) OR (from_id = ? AND to_id = ?) ORDER BY created_at ASC',
            (user['id'], other_id, other_id, user['id'])
        )
        rows = await cur.fetchall()
        msgs = [{'user_id': r[0], 'to_id': r[1], 'text': r[2], 'created_at': r[3]} for r in rows]
        return {'read_only': banned, 'messages': msgs}


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
