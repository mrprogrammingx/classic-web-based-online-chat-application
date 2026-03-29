import time
from fastapi import FastAPI, HTTPException, Depends, Request, Header, Response, Cookie
from fastapi.responses import RedirectResponse, JSONResponse
from fastapi.responses import FileResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from fastapi.staticfiles import StaticFiles
import aiosqlite
from db import init_db
import db as db_mod
import uuid
from core.utils import (
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
from core.config import SESSION_COOKIE_NAME, SESSION_DEFAULT_EXPIRES_SECONDS
from routers import register_routers
import os

app = FastAPI()


@app.middleware('http')
async def protect_home(request: Request, call_next):
    # Prevent anonymous access to the public home page HTML. If the request
    # targets /static/home.html require a valid token (Authorization header
    # or session cookie) and an existing session record (jti). Otherwise
    # redirect to the chat page.
    try:
        path = request.url.path
    except Exception:
        path = None
    if path == '/static/home.html':
        token_val = None
        auth = request.headers.get('authorization')
        if auth:
            token_val = auth.replace('Bearer ', '')
        else:
            token_val = request.cookies.get(SESSION_COOKIE_NAME)

        if not token_val:
            return RedirectResponse(url='/static/auth/login.html')

        try:
            data = verify_token(token_val)
        except Exception:
            return RedirectResponse(url='/static/auth/login.html')

        jti = data.get('jti')
        if not jti or not await session_exists(jti):
            return RedirectResponse(url='/static/auth/login.html')

    return await call_next(request)


# Explicitly handle requests for the public home HTML so a direct browser
# request cannot bypass protection if a server process was started before
# the middleware was deployed. This route runs before the StaticFiles mount
# and will serve the file only for authorized sessions.
@app.get('/static/home.html')
async def guarded_home(request: Request):
    # reuse the same authorization checks as the middleware
    token_val = None
    auth = request.headers.get('authorization')
    if auth:
        token_val = auth.replace('Bearer ', '')
    else:
        token_val = request.cookies.get(SESSION_COOKIE_NAME)

    if not token_val:
        return RedirectResponse(url='/static/auth/login.html')

    try:
        data = verify_token(token_val)
    except Exception:
        return RedirectResponse(url='/static/auth/login.html')

    jti = data.get('jti')
    if not jti or not await session_exists(jti):
        return RedirectResponse(url='/static/auth/login.html')

    # authorized: return the static file directly
    return FileResponse(os.path.join('static', 'home.html'), media_type='text/html')


app.mount('/static', StaticFiles(directory='static'), name='static')


@app.exception_handler(StarletteHTTPException)
async def custom_404_handler(request: Request, exc: StarletteHTTPException):
    # Only override 404 responses; pass others through as JSON
    if exc.status_code == 404:
        # If the request is from an authenticated user, serve the full 404
        # page (which includes the site header). If not authenticated,
        # serve a no-header 404 so anonymous users don't see header UI.
        token_val = None
        auth = request.headers.get('authorization')
        if auth:
            token_val = auth.replace('Bearer ', '')
        else:
            token_val = request.cookies.get(SESSION_COOKIE_NAME)

        show_header = False
        if token_val:
            try:
                data = verify_token(token_val)
                jti = data.get('jti')
                if jti and await session_exists(jti):
                    show_header = True
            except Exception:
                show_header = False

        if show_header:
            return FileResponse(os.path.join('static', '404.html'), status_code=404, media_type='text/html')
        else:
            return FileResponse(os.path.join('static', '404_noheader.html'), status_code=404, media_type='text/html')
    return JSONResponse({'detail': exc.detail}, status_code=exc.status_code)

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
    async with aiosqlite.connect(db_mod.DB) as db:
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
    expires = int(time.time() + SESSION_DEFAULT_EXPIRES_SECONDS)
    ip = request.client.host if request.client else None
    ua = request.headers.get('user-agent')
    await store_session(jti, user['id'], expires, ip=ip, user_agent=ua)
    token = create_token({'id': user['id'], 'email': user['email'], 'username': user['username'], 'jti': jti}, exp_seconds=SESSION_DEFAULT_EXPIRES_SECONDS)
    resp = JSONResponse({'user': user, 'token': token})
    resp.set_cookie(key=SESSION_COOKIE_NAME, value=token, httponly=True, samesite='lax')
    return resp


@app.post('/login')
async def login(request: Request):
    body = await request.json()
    email = body.get('email')
    password = body.get('password')
    if not email or not password:
        raise HTTPException(status_code=400, detail='email and password required')
    async with aiosqlite.connect(db_mod.DB) as db:
        cur = await db.execute('SELECT id, email, username, password, is_admin FROM users WHERE email = ?', (email,))
        row = await cur.fetchone()
        if not row or not verify_pw(password, row[3]):
            raise HTTPException(status_code=401, detail='invalid credentials')
        user = {'id': row[0], 'email': row[1], 'username': row[2], 'is_admin': bool(row[4])}
    jti = str(uuid.uuid4())
    expires = int(time.time() + SESSION_DEFAULT_EXPIRES_SECONDS)
    ip = request.client.host if request.client else None
    ua = request.headers.get('user-agent')
    await store_session(jti, user['id'], expires, ip=ip, user_agent=ua)
    token = create_token({'id': user['id'], 'email': user['email'], 'username': user['username'], 'jti': jti}, exp_seconds=SESSION_DEFAULT_EXPIRES_SECONDS)
    resp = JSONResponse({'user': user, 'token': token})
    resp.set_cookie(key=SESSION_COOKIE_NAME, value=token, httponly=True, samesite='lax')
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
    async with aiosqlite.connect(db_mod.DB) as db:
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
    expires = int(time.time() + SESSION_DEFAULT_EXPIRES_SECONDS)
    ip = request.client.host if request.client else None
    ua = request.headers.get('user-agent')
    await store_session(jti, user['id'], expires, ip=ip, user_agent=ua)
    token = create_token({'id': user['id'], 'email': user['email'], 'username': user['username'], 'jti': jti}, exp_seconds=SESSION_DEFAULT_EXPIRES_SECONDS)
    resp = JSONResponse({'user': user, 'token': token})
    resp.set_cookie(key=SESSION_COOKIE_NAME, value=token, httponly=True, samesite='lax')
    return resp



@app.get('/me')
async def me(request: Request, data=Depends(require_auth)):
    # return full user metadata for the current session
    user_id = data.get('id')
    async with aiosqlite.connect(db_mod.DB) as db:
        cur = await db.execute('SELECT id, email, username, is_admin FROM users WHERE id = ?', (user_id,))
        row = await cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail='user not found')
        user = {'id': row[0], 'email': row[1], 'username': row[2], 'is_admin': bool(row[3])}
    return {'user': user}


@app.patch('/me')
async def me_patch(request: Request, data=Depends(require_auth)):
    # For now username is immutable; tests expect a 400 when attempting to change it.
    body = await request.json()
    if not isinstance(body, dict):
        raise HTTPException(status_code=400, detail='invalid payload')
    if 'username' in body:
        raise HTTPException(status_code=400, detail='username is immutable')
    # Accept other no-op updates for now
    return {'ok': True}


@app.post('/refresh')
async def refresh(request: Request, data=Depends(require_auth)):
    # issue a fresh token (keeps behavior similar to login/register)
    user_id = data.get('id')
    async with aiosqlite.connect(db_mod.DB) as db:
        cur = await db.execute('SELECT id, email, username, is_admin FROM users WHERE id = ?', (user_id,))
        row = await cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail='user not found')
        user = {'id': row[0], 'email': row[1], 'username': row[2], 'is_admin': bool(row[3])}
    # create a new session jti and store it
    jti = str(uuid.uuid4())
    expires = int(time.time() + SESSION_DEFAULT_EXPIRES_SECONDS)
    ip = request.client.host if request.client else None
    ua = request.headers.get('user-agent')
    await store_session(jti, user['id'], expires, ip=ip, user_agent=ua)
    token = create_token({'id': user['id'], 'email': user['email'], 'username': user['username'], 'jti': jti}, exp_seconds=SESSION_DEFAULT_EXPIRES_SECONDS)
    resp = JSONResponse({'user': user, 'token': token})
    resp.set_cookie(key=SESSION_COOKIE_NAME, value=token, httponly=True, samesite='lax')
    return resp



@app.post('/password/reset-request')
async def password_reset_request(request: Request):
    # Accepts { email } and creates a short-lived token. In TEST_MODE the token
    # will be returned in the response for easier testing; otherwise the
    # implementation assumes the token would be emailed to the user by an
    # out-of-band process.
    body = await request.json()
    email = body.get('email')
    if not email:
        raise HTTPException(status_code=400, detail='email required')
    async with aiosqlite.connect(db_mod.DB) as db:
        cur = await db.execute('SELECT id FROM users WHERE email = ?', (email,))
        row = await cur.fetchone()
        if not row:
            # don't reveal whether a user exists; respond with ok
            return {'ok': True}
        user_id = row[0]
        token = str(uuid.uuid4())
        expires = int(time.time() + 3600)  # 1 hour
        now = int(time.time())
        try:
            await db.execute('INSERT INTO password_resets (token, user_id, expires_at, created_at) VALUES (?, ?, ?, ?)', (token, user_id, expires, now))
            await db.commit()
        except Exception:
            # if insertion fails, still return ok (idempotent)
            pass
    resp = {'ok': True}
    # In TEST_MODE return token to simplify automated tests
    if os.getenv('TEST_MODE') == '1':
        resp['token'] = token
    return resp


@app.post('/password/reset')
async def password_reset(request: Request):
    # Accepts { token, password }
    body = await request.json()
    token = body.get('token')
    password = body.get('password')
    if not token or not password:
        raise HTTPException(status_code=400, detail='token and password required')
    async with aiosqlite.connect(db_mod.DB) as db:
        cur = await db.execute('SELECT user_id, expires_at FROM password_resets WHERE token = ?', (token,))
        row = await cur.fetchone()
        if not row:
            raise HTTPException(status_code=400, detail='invalid token')
        user_id, expires_at = row[0], row[1]
        if int(time.time()) > int(expires_at):
            # cleanup expired token
            await db.execute('DELETE FROM password_resets WHERE token = ?', (token,))
            await db.commit()
            raise HTTPException(status_code=400, detail='token expired')
        # update user password
        await db.execute('UPDATE users SET password = ? WHERE id = ?', (hash_pw(password), user_id))
        # remove token
        await db.execute('DELETE FROM password_resets WHERE token = ?', (token,))
        await db.commit()
    return {'ok': True}


@app.patch('/me/password')
async def change_own_password(request: Request, data=Depends(require_auth)):
    # Logged-in users can change their password by supplying current and new
    # passwords: { current_password, new_password }
    body = await request.json()
    current = body.get('current_password')
    newpw = body.get('new_password')
    if not current or not newpw:
        raise HTTPException(status_code=400, detail='current_password and new_password required')
    user_id = data.get('id')
    async with aiosqlite.connect(db_mod.DB) as db:
        cur = await db.execute('SELECT password FROM users WHERE id = ?', (user_id,))
        row = await cur.fetchone()
        if not row or not verify_pw(current, row[0]):
            raise HTTPException(status_code=401, detail='invalid current password')
        await db.execute('UPDATE users SET password = ? WHERE id = ?', (hash_pw(newpw), user_id))
        await db.commit()
    return {'ok': True}


@app.delete('/me')
async def delete_own_account(request: Request, data=Depends(require_auth)):
    """
    Delete the current user's account. This will remove the user row and
    rely on DB cascade rules to clean up related data (sessions, memberships,
    messages, etc.). Requires authentication.
    """
    user_id = data.get('id')
    import os
    async with aiosqlite.connect(db_mod.DB) as db:
        # remove sessions explicitly
        try:
            await db.execute('DELETE FROM sessions WHERE user_id = ?', (user_id,))
        except Exception:
            pass
        # Find rooms owned by this user and delete them (and their files/messages)
        try:
            cur = await db.execute('SELECT id FROM rooms WHERE owner_id = ?', (user_id,))
            rows = await cur.fetchall()
            room_ids = [r[0] for r in rows]
            for rid in room_ids:
                # delete files on disk tracked in room_files
                cur2 = await db.execute('SELECT id, path FROM room_files WHERE room_id = ?', (rid,))
                rf_rows = await cur2.fetchall()
                for rf in rf_rows:
                    fid, p = rf[0], rf[1]
                    try:
                        if not os.path.isabs(p):
                            p = os.path.join('uploads', p)
                        if os.path.exists(p):
                            os.remove(p)
                    except Exception:
                        pass
                # cleanup DB rows related to the room
                await db.execute('DELETE FROM room_files WHERE room_id = ?', (rid,))
                await db.execute('DELETE FROM message_files WHERE message_id IN (SELECT id FROM messages WHERE room_id = ?)', (rid,))
                await db.execute('DELETE FROM messages WHERE room_id = ?', (rid,))
                await db.execute('DELETE FROM memberships WHERE room_id = ?', (rid,))
                await db.execute('DELETE FROM room_admins WHERE room_id = ?', (rid,))
                await db.execute('DELETE FROM room_bans WHERE room_id = ?', (rid,))
                await db.execute('DELETE FROM rooms WHERE id = ?', (rid,))
        except Exception:
            # ignore room-cleanup errors and continue to attempt user deletion
            pass
        # remove user's memberships in other rooms and any admin entries
        try:
            await db.execute('DELETE FROM memberships WHERE user_id = ?', (user_id,))
            await db.execute('DELETE FROM room_admins WHERE user_id = ?', (user_id,))
            await db.execute('DELETE FROM room_bans WHERE banner_id = ? OR banned_id = ?', (user_id, user_id))
        except Exception:
            pass
        # finally, delete the user row
        cur = await db.execute('DELETE FROM users WHERE id = ?', (user_id,))
        await db.commit()
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail='user not found')
    # return ok; client should clear cookies / redirect to login
    resp = JSONResponse({'ok': True})
    resp.delete_cookie('token')
    return resp
