from fastapi import APIRouter, Request, Depends, HTTPException
from core.utils import require_auth
from services import friends_service

router = APIRouter()


@router.get('/friends')
async def list_friends(user=Depends(require_auth)):
    friends = await friends_service.list_friends_for_user(user['id'])
    return {'friends': friends}


@router.post('/friends/add')
async def add_friend(request: Request, user=Depends(require_auth)):
    body = await request.json()
    fid = body.get('friend_id')
    if not fid:
        raise HTTPException(status_code=400, detail='friend_id required')
    if fid == user['id']:
        raise HTTPException(status_code=400, detail="can't add yourself")
    try:
        await friends_service.add_friend_relation(user['id'], fid)
    except Exception as e:
        # IntegrityError -> already friends
        raise HTTPException(status_code=409, detail=str(e))
    return {'ok': True}


@router.post('/friends/request')
async def send_friend_request(request: Request, user=Depends(require_auth)):
    body = await request.json()
    username = body.get('username')
    fid = body.get('friend_id')
    message = body.get('message')
    try:
        await friends_service.create_friend_request(user['id'], username, fid, message)
    except LookupError:
        raise HTTPException(status_code=404, detail='user not found')
    except ValueError as e:
        # some ValueErrors indicate a conflict (duplicate request or already friends)
        msg = str(e)
        if 'friend request already pending' in msg or 'already friends' in msg:
            raise HTTPException(status_code=409, detail=msg)
        raise HTTPException(status_code=400, detail=msg)
    except PermissionError:
        raise HTTPException(status_code=403, detail='ban exists between users')
    except Exception:
        raise HTTPException(status_code=409, detail='request already exists')
    return {'ok': True}


@router.get('/friends/requests')
async def list_incoming_requests(user=Depends(require_auth)):
    reqs = await friends_service.list_incoming_requests_for_user(user['id'])
    return {'requests': reqs}


@router.post('/friends/requests/respond')
async def respond_request(request: Request, user=Depends(require_auth)):
    body = await request.json()
    rid = body.get('request_id')
    action = body.get('action')  # 'accept' or 'reject'
    if not rid or action not in ('accept', 'reject'):
        raise HTTPException(status_code=400, detail='request_id and action required')
    try:
        await friends_service.respond_to_request(user['id'], rid, action)
    except LookupError:
        raise HTTPException(status_code=404, detail='request not found')
    return {'ok': True}


@router.post('/ban')
async def ban_user(request: Request, user=Depends(require_auth)):
    body = await request.json()
    bid = body.get('banned_id')
    if not bid:
        raise HTTPException(status_code=400, detail='banned_id required')
    if bid == user['id']:
        raise HTTPException(status_code=400, detail="can't ban yourself")
    await friends_service.ban_user_action(user['id'], bid)
    return {'ok': True}


@router.get('/bans/check')
async def check_ban(other_id: int, user=Depends(require_auth)):
    banned = await friends_service.check_ban_for_users(user['id'], other_id)
    return {'banned': banned}


@router.get('/bans')
async def list_bans(user=Depends(require_auth)):
    bans = await friends_service.list_bans_for_user(user['id'])
    return {'banned': bans}


@router.post('/unban')
async def unban_user(request: Request, user=Depends(require_auth)):
    body = await request.json()
    bid = body.get('banned_id')
    if not bid:
        raise HTTPException(status_code=400, detail='banned_id required')
    await friends_service.unban_user_action(user['id'], bid)
    return {'ok': True}


@router.post('/friends/remove')
async def remove_friend(request: Request, user=Depends(require_auth)):
    body = await request.json()
    fid = body.get('friend_id')
    if not fid:
        raise HTTPException(status_code=400, detail='friend_id required')
    await friends_service.remove_friend_action(user['id'], fid)
    return {'ok': True}
