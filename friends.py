from fastapi import APIRouter, Request, Depends, HTTPException
import aiosqlite
from utils import require_auth
from db import DB
import time

router = APIRouter()


@router.get('/friends')
async def list_friends(user=Depends(require_auth)):
    async with aiosqlite.connect(DB) as db:
        cur = await db.execute('SELECT u.id, u.email, u.username, u.is_admin FROM users u JOIN friends f ON f.friend_id = u.id WHERE f.user_id = ?', (user['id'],))
        rows = await cur.fetchall()
        friends = [{'id': r[0], 'email': r[1], 'username': r[2], 'is_admin': bool(r[3])} for r in rows]
        return {'friends': friends}


@router.post('/friends/add')
async def add_friend(request: Request, user=Depends(require_auth)):
    body = await request.json()
    fid = body.get('friend_id')
    if not fid:
        raise HTTPException(status_code=400, detail='friend_id required')
    if fid == user['id']:
        raise HTTPException(status_code=400, detail="can't add yourself")
    async with aiosqlite.connect(DB) as db:
        # check for bans either direction
        cur = await db.execute('SELECT 1 FROM bans WHERE (banner_id = ? AND banned_id = ?) OR (banner_id = ? AND banned_id = ?)', (user['id'], fid, fid, user['id']))
        if await cur.fetchone():
            raise HTTPException(status_code=403, detail='ban exists between users')
        try:
            await db.execute('INSERT INTO friends (user_id, friend_id, created_at) VALUES (?, ?, ?)', (user['id'], fid, int(time.time())))
            await db.commit()
        except aiosqlite.IntegrityError:
            raise HTTPException(status_code=409, detail='already friends')
    return {'ok': True}


@router.post('/friends/request')
async def send_friend_request(request: Request, user=Depends(require_auth)):
    """Send a friend request by username (or id). Body: { username?: str, friend_id?: int, message?: str }"""
    body = await request.json()
    username = body.get('username')
    fid = body.get('friend_id')
    message = body.get('message')
    async with aiosqlite.connect(DB) as db:
        if username and not fid:
            cur = await db.execute('SELECT id FROM users WHERE username = ?', (username,))
            row = await cur.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail='user not found')
            fid = row[0]
        if not fid:
            raise HTTPException(status_code=400, detail='username or friend_id required')
        if fid == user['id']:
            raise HTTPException(status_code=400, detail="can't request yourself")
        # check for existing ban (either direction)
        cur = await db.execute('SELECT 1 FROM bans WHERE (banner_id = ? AND banned_id = ?) OR (banner_id = ? AND banned_id = ?)', (user['id'], fid, fid, user['id']))
        if await cur.fetchone():
            raise HTTPException(status_code=403, detail='ban exists between users')
        # create request
        try:
            await db.execute('INSERT INTO friend_requests (from_id, to_id, message, created_at) VALUES (?, ?, ?, ?)', (user['id'], fid, message, int(time.time())))
            await db.commit()
        except aiosqlite.IntegrityError:
            raise HTTPException(status_code=409, detail='request already exists')
    return {'ok': True}


@router.get('/friends/requests')
async def list_incoming_requests(user=Depends(require_auth)):
    async with aiosqlite.connect(DB) as db:
        cur = await db.execute('SELECT fr.id, fr.from_id, u.username, u.email, fr.message, fr.status, fr.created_at FROM friend_requests fr JOIN users u ON u.id = fr.from_id WHERE fr.to_id = ? AND fr.status = ?', (user['id'], 'pending'))
        rows = await cur.fetchall()
        reqs = [{'id': r[0], 'from_id': r[1], 'username': r[2], 'email': r[3], 'message': r[4], 'status': r[5], 'created_at': r[6]} for r in rows]
        return {'requests': reqs}


@router.post('/friends/requests/respond')
async def respond_request(request: Request, user=Depends(require_auth)):
    body = await request.json()
    rid = body.get('request_id')
    action = body.get('action')  # 'accept' or 'reject'
    if not rid or action not in ('accept', 'reject'):
        raise HTTPException(status_code=400, detail='request_id and action required')
    async with aiosqlite.connect(DB) as db:
        cur = await db.execute('SELECT from_id, to_id FROM friend_requests WHERE id = ? AND to_id = ? AND status = ?', (rid, user['id'], 'pending'))
        row = await cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail='request not found')
        from_id = row[0]
        if action == 'reject':
            await db.execute('UPDATE friend_requests SET status = ? WHERE id = ?', ('rejected', rid))
            await db.commit()
            return {'ok': True}
        # accept: create mutual friendship entries (both directions)
        await db.execute('UPDATE friend_requests SET status = ? WHERE id = ?', ('accepted', rid))
        try:
            await db.execute('INSERT INTO friends (user_id, friend_id, created_at) VALUES (?, ?, ?)', (user['id'], from_id, int(time.time())))
        except aiosqlite.IntegrityError:
            pass
        try:
            await db.execute('INSERT INTO friends (user_id, friend_id, created_at) VALUES (?, ?, ?)', (from_id, user['id'], int(time.time())))
        except aiosqlite.IntegrityError:
            pass
        await db.commit()
    return {'ok': True}


@router.post('/ban')
async def ban_user(request: Request, user=Depends(require_auth)):
    body = await request.json()
    bid = body.get('banned_id')
    if not bid:
        raise HTTPException(status_code=400, detail='banned_id required')
    if bid == user['id']:
        raise HTTPException(status_code=400, detail="can't ban yourself")
    async with aiosqlite.connect(DB) as db:
        try:
            await db.execute('INSERT INTO bans (banner_id, banned_id, created_at) VALUES (?, ?, ?)', (user['id'], bid, int(time.time())))
            # remove friendships both directions
            await db.execute('DELETE FROM friends WHERE (user_id = ? AND friend_id = ?) OR (user_id = ? AND friend_id = ?)', (user['id'], bid, bid, user['id']))
            # remove pending friend requests both directions
            await db.execute('DELETE FROM friend_requests WHERE (from_id = ? AND to_id = ?) OR (from_id = ? AND to_id = ?)', (user['id'], bid, bid, user['id']))
            await db.commit()
        except aiosqlite.IntegrityError:
            # already banned
            pass
    return {'ok': True}


@router.get('/bans/check')
async def check_ban(other_id: int, user=Depends(require_auth)):
    async with aiosqlite.connect(DB) as db:
        cur = await db.execute('SELECT 1 FROM bans WHERE (banner_id = ? AND banned_id = ?) OR (banner_id = ? AND banned_id = ?)', (user['id'], other_id, other_id, user['id']))
        row = await cur.fetchone()
        return {'banned': bool(row)}


@router.post('/friends/remove')
async def remove_friend(request: Request, user=Depends(require_auth)):
    body = await request.json()
    fid = body.get('friend_id')
    if not fid:
        raise HTTPException(status_code=400, detail='friend_id required')
    async with aiosqlite.connect(DB) as db:
        await db.execute('DELETE FROM friends WHERE user_id = ? AND friend_id = ?', (user['id'], fid))
        await db.commit()
    return {'ok': True}
