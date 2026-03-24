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
async def list_rooms():
    async with aiosqlite.connect(DB) as db:
        cur = await db.execute("SELECT id, owner_id, name, description, visibility, created_at FROM rooms WHERE visibility = 'public' ORDER BY created_at DESC")
        rows = await cur.fetchall()
        rooms = [{'id': r[0], 'owner_id': r[1], 'name': r[2], 'description': r[3], 'visibility': r[4], 'created_at': r[5]} for r in rows]
        return {'rooms': rooms}


@router.get('/rooms/{room_id}')
async def get_room(room_id: int, user=Depends(require_auth)):
    async with aiosqlite.connect(DB) as db:
        cur = await db.execute('SELECT id, owner_id, name, description, visibility, created_at FROM rooms WHERE id = ?', (room_id,))
        row = await cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail='room not found')
        room = {'id': row[0], 'owner_id': row[1], 'name': row[2], 'description': row[3], 'visibility': row[4], 'created_at': row[5]}
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
        await db.execute('DELETE FROM memberships WHERE room_id = ? AND user_id = ?', (room_id, user['id']))
        # also remove from admins if present
        await db.execute('DELETE FROM room_admins WHERE room_id = ? AND user_id = ?', (room_id, user['id']))
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
        await db.execute('INSERT OR IGNORE INTO room_bans (room_id, banned_id, created_at) VALUES (?, ?, ?)', (room_id, uid, int(time.time())))
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
