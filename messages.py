from fastapi import APIRouter, Request, Depends, HTTPException
import aiosqlite
from db import DB
from utils import require_auth
import time

router = APIRouter()


@router.post('/messages/send')
async def send_private_message(request: Request, user=Depends(require_auth)):
    """Send a private message to another user. Body: { to_id, text }"""
    body = await request.json()
    to_id = body.get('to_id')
    text = body.get('text')
    if not to_id or not text:
        raise HTTPException(status_code=400, detail='to_id and text required')
    if to_id == user['id']:
        raise HTTPException(status_code=400, detail="can't message yourself")

    async with aiosqlite.connect(DB) as db:
        # ban check (either direction)
        cur = await db.execute(
            'SELECT 1 FROM bans WHERE (banner_id = ? AND banned_id = ?) OR (banner_id = ? AND banned_id = ?)',
            (user['id'], to_id, to_id, user['id'])
        )
        if await cur.fetchone():
            raise HTTPException(status_code=403, detail='ban exists between users')

        # require mutual friendship
        cur = await db.execute('SELECT 1 FROM friends WHERE user_id = ? AND friend_id = ?', (user['id'], to_id))
        a = await cur.fetchone()
        cur = await db.execute('SELECT 1 FROM friends WHERE user_id = ? AND friend_id = ?', (to_id, user['id']))
        b = await cur.fetchone()
        if not (a and b):
            raise HTTPException(status_code=403, detail='users not friends')

        # insert message
        await db.execute('INSERT INTO private_messages (from_id, to_id, text, created_at) VALUES (?, ?, ?, ?)',
                         (user['id'], to_id, text, int(time.time())))
        await db.commit()

    return {'ok': True}


@router.get('/messages/history')
async def private_history(with_id: int, user=Depends(require_auth)):
    """Return private message history between authenticated user and with_id.

    Response: { read_only: bool, messages: [ { from_id, to_id, text, created_at } ] }
    """
    async with aiosqlite.connect(DB) as db:
        # check if ban exists either direction
        cur = await db.execute(
            'SELECT 1 FROM bans WHERE (banner_id = ? AND banned_id = ?) OR (banner_id = ? AND banned_id = ?)',
            (user['id'], with_id, with_id, user['id'])
        )
        banned = bool(await cur.fetchone())
        # fetch messages from private_messages table
        cur = await db.execute(
            'SELECT from_id, to_id, text, created_at FROM private_messages WHERE (from_id = ? AND to_id = ?) OR (from_id = ? AND to_id = ?) ORDER BY created_at ASC',
            (user['id'], with_id, with_id, user['id'])
        )
        rows = await cur.fetchall()
        msgs = [{'from_id': r[0], 'to_id': r[1], 'text': r[2], 'created_at': r[3]} for r in rows]
        return {'read_only': banned, 'messages': msgs}
