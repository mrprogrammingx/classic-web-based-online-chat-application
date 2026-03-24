from fastapi import APIRouter, Request, Depends, HTTPException
from utils import require_auth, touch_tab, remove_tab, get_presence_status, get_presence_statuses, list_sessions_for_user, remove_session_by_jti

router = APIRouter()


@router.post('/presence/heartbeat')
async def heartbeat(request: Request, body: dict = None, user=Depends(require_auth)):
    # body should contain tab_id and jti
    data = await request.json()
    tab_id = data.get('tab_id')
    jti = data.get('jti')
    if not tab_id or not jti:
        raise HTTPException(status_code=400, detail='tab_id and jti required')
    ip = request.client.host if request.client else None
    ua = request.headers.get('user-agent')
    await touch_tab(tab_id, jti, user['id'], ip=ip, user_agent=ua)
    return {'ok': True}


@router.post('/presence/close')
async def close_tab(request: Request, user=Depends(require_auth)):
    data = await request.json()
    tab_id = data.get('tab_id')
    if not tab_id:
        raise HTTPException(status_code=400, detail='tab_id required')
    await remove_tab(tab_id)
    return {'ok': True}


@router.get('/presence/{user_id}')
async def presence_status(user_id: int):
    return {'status': await get_presence_status(user_id)}


@router.get('/presence')
async def presence_batch(ids: str = None):
    """Batch presence lookup. Query param `ids` is a comma-separated list of user ids.

    Returns: { statuses: { '<id>': 'online'|'AFK'|'offline', ... } }
    """
    if not ids:
        return {'statuses': {}}
    parts = [p.strip() for p in ids.split(',') if p.strip()]
    uids = []
    for p in parts:
        try:
            uids.append(int(p))
        except Exception:
            continue
    statuses = await get_presence_statuses(uids)
    return {'statuses': statuses}


@router.get('/sessions')
async def my_sessions(user=Depends(require_auth)):
    return {'sessions': await list_sessions_for_user(user['id'])}


@router.post('/sessions/revoke')
async def revoke_session(request: Request, user=Depends(require_auth)):
    data = await request.json()
    jti = data.get('jti')
    if not jti:
        raise HTTPException(status_code=400, detail='jti required')
    # only allow revoking sessions owned by this user
    sessions = await list_sessions_for_user(user['id'])
    if not any(s['jti'] == jti for s in sessions):
        raise HTTPException(status_code=403, detail='not your session')
    await remove_session_by_jti(jti)
    return {'ok': True}
