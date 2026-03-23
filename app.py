import time
from fastapi import FastAPI, HTTPException, Depends, Request, Header, Response, Cookie
from fastapi.responses import RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
import aiosqlite
from db import init_db, DB
import uuid
from utils import (
    hash_pw,
    verify_pw,
    create_token,
    verify_token,
    store_session,
    remove_session,
    session_exists,
    update_session_expiry,
    require_auth,
)
from presence import router as presence_router
from admin import router as admin_router

app = FastAPI()

# serve static files (demo UI)
app.mount('/static', StaticFiles(directory='static'), name='static')

@app.on_event('startup')
async def startup():
    await init_db()


@app.get('/')
async def root():
    return RedirectResponse(url='/static/index.html')

async def require_auth(authorization: str = Header(None), token_cookie: str = Cookie(None)):
    token = None
    if authorization:
        token = authorization.replace('Bearer ', '')
    elif token_cookie:
        token = token_cookie
    if not token:
        raise HTTPException(status_code=401, detail='missing token')
    try:
        data = verify_token(token)
    except Exception:
        raise HTTPException(status_code=401, detail='invalid token')
    # ensure the session (jti) still exists
    jti = data.get('jti')
    if not jti or not await session_exists(jti):
        raise HTTPException(status_code=401, detail='invalid or expired session')
    return data

@app.post('/register')
async def register(request: Request):
    body = await request.json()
    email = body.get('email')
    username = body.get('username')
    password = body.get('password')
    if not email or not username or not password:
        raise HTTPException(status_code=400, detail='email, username and password required')
    async with aiosqlite.connect(DB) as db:
        try:
            await db.execute('INSERT INTO users (email, username, password, created_at) VALUES (?, ?, ?, ?)',
                             (email, username, hash_pw(password), int(time.time())))
            await db.commit()
        except aiosqlite.IntegrityError:
            raise HTTPException(status_code=409, detail='email or username taken')
        cur = await db.execute('SELECT id, email, username FROM users WHERE email = ?', (email,))
        row = await cur.fetchone()
        user = {'id': row[0], 'email': row[1], 'username': row[2]}
    # create session jti and token
    jti = str(uuid.uuid4())
    expires = int(time.time() + 3600*24*30)
    ip = request.client.host if request.client else None
    ua = request.headers.get('user-agent')
    await store_session(jti, user['id'], expires, ip=ip, user_agent=ua)
    token = create_token({'id': user['id'], 'email': user['email'], 'username': user['username'], 'jti': jti}, exp_seconds=3600*24*30)
    # set HttpOnly cookie for persistent login across browser close/reopen
    resp = JSONResponse({'user': user, 'token': token})
    resp.set_cookie(key='token', value=token, httponly=True, samesite='lax')
    return resp

@app.post('/login')
async def login(request: Request):
    body = await request.json()
    email = body.get('email')
    password = body.get('password')
    if not email or not password:
        raise HTTPException(status_code=400, detail='email and password required')
    async with aiosqlite.connect(DB) as db:
        cur = await db.execute('SELECT id, email, username, password FROM users WHERE email = ?', (email,))
        row = await cur.fetchone()
        if not row or not verify_pw(password, row[3]):
            raise HTTPException(status_code=401, detail='invalid credentials')
        user = {'id': row[0], 'email': row[1], 'username': row[2]}
    jti = str(uuid.uuid4())
    expires = int(time.time() + 3600*24*30)
    ip = request.client.host if request.client else None
    ua = request.headers.get('user-agent')
    await store_session(jti, user['id'], expires, ip=ip, user_agent=ua)
    token = create_token({'id': user['id'], 'email': user['email'], 'username': user['username'], 'jti': jti}, exp_seconds=3600*24*30)
    resp = JSONResponse({'user': user, 'token': token})
    resp.set_cookie(key='token', value=token, httponly=True, samesite='lax')
    return resp

@app.post('/logout')
async def logout(authorization: str = Header(None), token_cookie: str = Cookie(None)):
    token = None
    if authorization:
        token = authorization.replace('Bearer ', '')
    elif token_cookie:
        token = token_cookie
    if not token:
        raise HTTPException(status_code=401, detail='missing token')
    try:
        data = verify_token(token)
    except Exception:
        raise HTTPException(status_code=401, detail='invalid token')
    jti = data.get('jti')
    if jti:
        await remove_session(jti)
    resp = JSONResponse({'ok': True})
    resp.delete_cookie('token')
    return resp


# include presence/session router
app.include_router(presence_router)
app.include_router(admin_router)

@app.post('/refresh')
async def refresh(authorization: str = Header(None), token_cookie: str = Cookie(None)):
    token = None
    if authorization:
        token = authorization.replace('Bearer ', '')
    elif token_cookie:
        token = token_cookie
    if not token:
        raise HTTPException(status_code=401, detail='missing token')
    try:
        data = verify_token(token)
    except Exception:
        raise HTTPException(status_code=401, detail='invalid token')
    jti = data.get('jti')
    if not jti or not await session_exists(jti):
        raise HTTPException(status_code=401, detail='invalid or expired session')
    # extend session
    new_expires = int(time.time() + 3600*24*30)
    await update_session_expiry(jti, new_expires)
    new_token = create_token({'id': data['id'], 'email': data['email'], 'username': data['username'], 'jti': jti}, exp_seconds=3600*24*30)
    resp = JSONResponse({'token': new_token})
    resp.set_cookie('token', new_token, httponly=True, samesite='lax')
    return resp

@app.post('/password-reset')
async def password_reset(request: Request):
    body = await request.json()
    email = body.get('email')
    if not email:
        raise HTTPException(status_code=400, detail='email required')
    # For simplicity: issue a short-lived reset token and return it (in real apps, email it)
    async with aiosqlite.connect(DB) as db:
        cur = await db.execute('SELECT id, email FROM users WHERE email = ?', (email,))
        row = await cur.fetchone()
        if not row:
            return {'ok': True}
        token = create_token({'id': row[0], 'email': row[1], 'purpose': 'reset'}, exp_seconds=3600)
        return {'reset_token': token}

@app.post('/password-change')
async def password_change(request: Request, user=Depends(require_auth)):
    body = await request.json()
    old = body.get('old_password')
    new = body.get('new_password')
    if not old or not new:
        raise HTTPException(status_code=400, detail='old and new password required')
    async with aiosqlite.connect(DB) as db:
        cur = await db.execute('SELECT password FROM users WHERE id = ?', (user['id'],))
        row = await cur.fetchone()
        if not row or not verify_pw(old, row[0]):
            raise HTTPException(status_code=401, detail='invalid credentials')
        await db.execute('UPDATE users SET password = ? WHERE id = ?', (hash_pw(new), user['id']))
        await db.commit()
        return {'ok': True}

@app.post('/delete-account')
async def delete_account(user=Depends(require_auth)):
    uid = user['id']
    async with aiosqlite.connect(DB) as db:
        # find rooms owned by user
        cur = await db.execute('SELECT id FROM rooms WHERE owner_id = ?', (uid,))
        rooms = await cur.fetchall()
        room_ids = [r[0] for r in rooms]
        # delete rooms (messages cascade)
        for rid in room_ids:
            await db.execute('DELETE FROM rooms WHERE id = ?', (rid,))
        # remove memberships in other rooms
        await db.execute('DELETE FROM memberships WHERE user_id = ?', (uid,))
        # remove sessions
        await db.execute('DELETE FROM sessions WHERE user_id = ?', (uid,))
        # delete user
        await db.execute('DELETE FROM users WHERE id = ?', (uid,))
        await db.commit()
        return {'ok': True}


@app.patch('/me')
async def update_profile(request: Request, user=Depends(require_auth)):
    """Update the authenticated user's profile.

    Rules enforced:
    - Username is immutable after registration. Any attempt to include `username` in the
      request body will be rejected with HTTP 400.
    - Email may be updated without verification (by design for this project).
    """
    body = await request.json()
    # explicit rule: username cannot be changed
    if 'username' in body:
        raise HTTPException(status_code=400, detail='username is immutable after registration')

    email = body.get('email')
    if not email:
        raise HTTPException(status_code=400, detail='nothing to update')

    async with aiosqlite.connect(DB) as db:
        try:
            await db.execute('UPDATE users SET email = ? WHERE id = ?', (email, user['id']))
            await db.commit()
        except aiosqlite.IntegrityError:
            # unique constraint on email
            raise HTTPException(status_code=409, detail='email already taken')
        cur = await db.execute('SELECT id, email, username FROM users WHERE id = ?', (user['id'],))
        row = await cur.fetchone()
        return {'user': {'id': row[0], 'email': row[1], 'username': row[2]}}


@app.get('/me')
async def me(user=Depends(require_auth)):
    """Return authoritative user metadata for the currently authenticated user.

    This includes the `is_admin` flag so the client can decide whether to
    reveal admin UI elements.
    """
    async with aiosqlite.connect(DB) as db:
        cur = await db.execute('SELECT id, email, username, is_admin FROM users WHERE id = ?', (user['id'],))
        row = await cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail='user not found')
        return {'user': {'id': row[0], 'email': row[1], 'username': row[2], 'is_admin': bool(row[3])}}
