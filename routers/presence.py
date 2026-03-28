from fastapi import APIRouter, Request, Depends, HTTPException
import logging
from core.logging_setup import ensure_file_handler
from core.utils import require_auth, touch_tab, remove_tab, get_presence_status, get_presence_statuses, list_sessions_for_user, remove_session_by_jti

# module logger
logger = logging.getLogger(__name__)
ensure_file_handler(logger)

router = APIRouter()


@router.post('/presence/heartbeat')
async def heartbeat(request: Request, body: dict = None, user=Depends(require_auth)):
    # Temporary debug logging: record that a heartbeat arrived and whether
    # Cookie/Authorization headers were present. Do NOT log token values.
    try:
        data = await request.json()
    except Exception:
        data = {}
    tab_id = data.get('tab_id')
    jti = data.get('jti')
    has_cookie = 'cookie' in (h.lower() for h in request.headers.keys())
    has_auth = 'authorization' in (h.lower() for h in request.headers.keys())
    logger.info('heartbeat received: keys=%s has_cookie=%s has_auth=%s', list(data.keys()), has_cookie, has_auth)
    # If client is using cookie-based (HttpOnly) sessions it may not be able to
    # read the token/jti. In that case fall back to the authenticated token's
    # jti provided by the dependency `require_auth`.
    if not jti:
        jti = user.get('jti') if isinstance(user, dict) else None
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
    sessions = await list_sessions_for_user(user['id'])
    if not any(s['jti'] == jti for s in sessions):
        raise HTTPException(status_code=403, detail='not your session')
    await remove_session_by_jti(jti)
    return {'ok': True}
