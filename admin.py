from fastapi import APIRouter, Depends, HTTPException
import aiosqlite
from utils import require_auth
from db import DB

router = APIRouter()


async def require_admin(user=Depends(require_auth)):
    # check user is admin
    async with aiosqlite.connect(DB) as db:
        cur = await db.execute('SELECT is_admin FROM users WHERE id = ?', (user['id'],))
        row = await cur.fetchone()
        if not row or not row[0]:
            raise HTTPException(status_code=403, detail='admin required')
    return user


@router.get('/admin/users')
async def list_users(user=Depends(require_admin)):
    async with aiosqlite.connect(DB) as db:
        cur = await db.execute('SELECT id, email, username, created_at, is_admin FROM users')
        rows = await cur.fetchall()
        return {'users': [{'id': r[0], 'email': r[1], 'username': r[2], 'created_at': r[3], 'is_admin': bool(r[4])} for r in rows]}


@router.post('/admin/users/delete')
async def delete_user(request, user=Depends(require_admin)):
    body = await request.json()
    uid = body.get('id')
    if not uid:
        raise HTTPException(status_code=400, detail='id required')
    async with aiosqlite.connect(DB) as db:
        await db.execute('DELETE FROM users WHERE id = ?', (uid,))
        await db.commit()
    return {'ok': True}


@router.post('/admin/users/promote')
async def promote_user(request, user=Depends(require_admin)):
    """Promote a user to admin. Body: { id: <user_id> }"""
    body = await request.json()
    uid = body.get('id')
    if not uid:
        raise HTTPException(status_code=400, detail='id required')
    async with aiosqlite.connect(DB) as db:
        await db.execute('UPDATE users SET is_admin = 1 WHERE id = ?', (uid,))
        await db.commit()
    return {'ok': True}
