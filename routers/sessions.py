from fastapi import APIRouter, Request, HTTPException, Depends
import aiosqlite
from db import DB
from core.utils import require_auth, list_sessions_for_user, remove_session_by_jti

router = APIRouter()


@router.get('/sessions')
async def get_sessions(data=Depends(require_auth)):
    user_id = data.get('id')
    sessions = await list_sessions_for_user(user_id)
    return {'sessions': sessions}


@router.post('/sessions/revoke')
async def revoke_session(request: Request, data=Depends(require_auth)):
    body = await request.json()
    jti = body.get('jti')
    if not jti:
        raise HTTPException(status_code=400, detail='jti required')
    # Ensure the session belongs to the user
    async with aiosqlite.connect(DB) as db:
        cur = await db.execute('SELECT user_id FROM sessions WHERE jti = ?', (jti,))
        row = await cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail='session not found')
        if row[0] != data.get('id'):
            raise HTTPException(status_code=403, detail='forbidden')
    await remove_session_by_jti(jti)
    return {'ok': True}
