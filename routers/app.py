import time
from fastapi import FastAPI, HTTPException, Depends, Request, Header, Response, Cookie
from fastapi.responses import RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
import aiosqlite
from db import init_db, DB
import uuid
from routers.utils import (
    hash_pw,
    verify_pw,
    create_token,
    verify_token,
    store_session,
    remove_session,
    session_exists,
    update_session_expiry,
    require_auth,
    presence_online_seconds,
)
from routers import register_routers
import os

app = FastAPI()

app.mount('/static', StaticFiles(directory='static'), name='static')

@app.on_event('startup')
async def startup():
    await init_db()


@app.get('/')
async def root():
    return RedirectResponse(url='/static/chat/index.html')

# Authentication endpoints and test helpers

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
        cur = await db.execute('SELECT id, email, username, is_admin FROM users WHERE email = ?', (email,))
        row = await cur.fetchone()
        user = {'id': row[0], 'email': row[1], 'username': row[2], 'is_admin': bool(row[3])}
    jti = str(uuid.uuid4())
    expires = int(time.time() + 3600*24*30)
    ip = request.client.host if request.client else None
    ua = request.headers.get('user-agent')
    await store_session(jti, user['id'], expires, ip=ip, user_agent=ua)
    token = create_token({'id': user['id'], 'email': user['email'], 'username': user['username'], 'jti': jti}, exp_seconds=3600*24*30)
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
        cur = await db.execute('SELECT id, email, username, password, is_admin FROM users WHERE email = ?', (email,))
        row = await cur.fetchone()
        if not row or not verify_pw(password, row[3]):
            raise HTTPException(status_code=401, detail='invalid credentials')
        user = {'id': row[0], 'email': row[1], 'username': row[2], 'is_admin': bool(row[4])}
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
async def logout(authorization: str = Header(None), token: str = Cookie(None)):
    token_val = None
    if authorization:
        token_val = authorization.replace('Bearer ', '')
    elif token:
        token_val = token
    if not token_val:
        raise HTTPException(status_code=401, detail='missing token')
    try:
        data = verify_token(token_val)
    except Exception:
        raise HTTPException(status_code=401, detail='invalid token')
    jti = data.get('jti')
    if jti:
        await remove_session(jti)
    resp = JSONResponse({'ok': True})
    resp.delete_cookie('token')
    return resp


register_routers(app)


@app.post('/_test/create_user')
async def create_test_user(request: Request):
    if os.getenv('TEST_MODE') != '1':
        raise HTTPException(status_code=404, detail='not found')
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
            cur = await db.execute('SELECT id, email, username, is_admin FROM users WHERE email = ?', (email,))
            row = await cur.fetchone()
            if not row:
                cur = await db.execute('SELECT id, email, username, is_admin FROM users WHERE username = ?', (username,))
                row = await cur.fetchone()
            if not row:
                raise HTTPException(status_code=409, detail='user exists but lookup failed')
            user = {'id': row[0], 'email': row[1], 'username': row[2], 'is_admin': bool(row[3])}
        else:
            cur = await db.execute('SELECT id, email, username, is_admin FROM users WHERE email = ?', (email,))
            row = await cur.fetchone()
            user = {'id': row[0], 'email': row[1], 'username': row[2], 'is_admin': bool(row[3])}
    jti = str(uuid.uuid4())
    expires = int(time.time() + 3600*24*30)
    ip = request.client.host if request.client else None
    ua = request.headers.get('user-agent')
    await store_session(jti, user['id'], expires, ip=ip, user_agent=ua)
    token = create_token({'id': user['id'], 'email': user['email'], 'username': user['username'], 'jti': jti}, exp_seconds=3600*24*30)
    resp = JSONResponse({'user': user, 'token': token})
    resp.set_cookie(key='token', value=token, httponly=True, samesite='lax')
    return resp
