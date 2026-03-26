import time
import jwt
from passlib.context import CryptContext
import aiosqlite
from db import DB
from fastapi import HTTPException, Request
import os
from typing import List

pwd = CryptContext(schemes=['pbkdf2_sha256'], deprecated='auto')
JWT_SECRET = 'change_this_secret'
JWT_ALGO = 'HS256'

def presence_online_seconds():
    try:
        return int(os.getenv('PRESENCE_ONLINE_SECONDS', '60'))
    except Exception:
        return 60

def hash_pw(pw: str) -> str:
    return pwd.hash(pw)

def verify_pw(pw: str, h: str) -> bool:
    return pwd.verify(pw, h)

def create_token(payload: dict, exp_seconds: int = 3600*24*7):
    data = payload.copy()
    data['exp'] = int(time.time() + exp_seconds)
    if 'jti' in payload:
        data['jti'] = payload['jti']
    return jwt.encode(data, JWT_SECRET, algorithm=JWT_ALGO)

async def store_session(jti: str, user_id: int, expires_at: int, ip: str = None, user_agent: str = None, last_active: int = None):
    async with aiosqlite.connect(DB) as db:
        await db.execute('INSERT INTO sessions (jti, user_id, created_at, expires_at, ip, user_agent, last_active) VALUES (?, ?, ?, ?, ?, ?, ?)',
                         (jti, user_id, int(time.time()), expires_at, ip, user_agent, last_active or int(time.time())))
        await db.commit()

async def remove_session(jti: str):
    async with aiosqlite.connect(DB) as db:
        await db.execute('DELETE FROM sessions WHERE jti = ?', (jti,))
        await db.commit()

async def session_exists(jti: str):
    async with aiosqlite.connect(DB) as db:
        cur = await db.execute('SELECT jti FROM sessions WHERE jti = ?', (jti,))
        row = await cur.fetchone()
        return bool(row)

async def update_session_expiry(jti: str, expires_at: int):
    async with aiosqlite.connect(DB) as db:
        await db.execute('UPDATE sessions SET expires_at = ? WHERE jti = ?', (expires_at, jti))
        await db.commit()

def verify_token(token: str):
    return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGO])

async def get_user_by_email(email: str):
    async with aiosqlite.connect(DB) as db:
        cur = await db.execute('SELECT id, email, username, password FROM users WHERE email = ?', (email,))
        return await cur.fetchone()


async def require_auth(request: Request):
    auth = request.headers.get('authorization')
    cookie_token = request.cookies.get('token')
    token_val = None
    if auth:
        token_val = auth.replace('Bearer ', '')
    elif cookie_token:
        token_val = cookie_token
    if not token_val:
        raise HTTPException(status_code=401, detail='missing token')
    try:
        data = verify_token(token_val)
    except Exception:
        raise HTTPException(status_code=401, detail='invalid token')
    jti = data.get('jti')
    if not jti or not await session_exists(jti):
        raise HTTPException(status_code=401, detail='invalid or expired session')
    return data


async def list_sessions_for_user(user_id: int):
    async with aiosqlite.connect(DB) as db:
        cur = await db.execute('SELECT jti, created_at, expires_at, ip, user_agent, last_active FROM sessions WHERE user_id = ?', (user_id,))
        rows = await cur.fetchall()
        return [{'jti': r[0], 'created_at': r[1], 'expires_at': r[2], 'ip': r[3], 'user_agent': r[4], 'last_active': r[5]} for r in rows]


async def remove_session_by_jti(jti: str):
    await remove_session(jti)


async def touch_tab(tab_id: str, jti: str, user_id: int, ip: str = None, user_agent: str = None):
    now = int(time.time())
    async with aiosqlite.connect(DB) as db:
        try:
            await db.execute('INSERT INTO tab_presence (tab_id, jti, user_id, created_at, last_active, user_agent, ip) VALUES (?, ?, ?, ?, ?, ?, ?)',
                             (tab_id, jti, user_id, now, now, user_agent, ip))
        except aiosqlite.IntegrityError:
            await db.execute('UPDATE tab_presence SET last_active = ?, user_agent = ?, ip = ? WHERE tab_id = ?', (now, user_agent, ip, tab_id))
        await db.commit()


async def remove_tab(tab_id: str):
    async with aiosqlite.connect(DB) as db:
        await db.execute('DELETE FROM tab_presence WHERE tab_id = ?', (tab_id,))
        await db.commit()


async def get_presence_status(user_id: int):
    cutoff = int(time.time()) - presence_online_seconds()
    async with aiosqlite.connect(DB) as db:
        cur = await db.execute('SELECT COUNT(*) FROM tab_presence WHERE user_id = ?', (user_id,))
        total = (await cur.fetchone())[0]
        if total == 0:
            return 'offline'
        cur = await db.execute('SELECT COUNT(*) FROM tab_presence WHERE user_id = ? AND last_active > ?', (user_id, cutoff))
        active = (await cur.fetchone())[0]
        if active > 0:
            return 'online'
        return 'AFK'


async def get_presence_statuses(user_ids: list):
    if not user_ids:
        return {}
    cutoff = int(time.time()) - presence_online_seconds()
    placeholders = ','.join(['?'] * len(user_ids))
    sql = f"SELECT user_id, COUNT(*) as total, MAX(last_active) as last_active_max FROM tab_presence WHERE user_id IN ({placeholders}) GROUP BY user_id"
    params = list(user_ids)
    out = {}
    async with aiosqlite.connect(DB) as db:
        cur = await db.execute(sql, tuple(params))
        rows = await cur.fetchall()
        found = set()
        for r in rows:
            uid, total, last_active_max = r[0], r[1], r[2]
            found.add(uid)
            if total == 0:
                out[str(uid)] = 'offline'
            elif last_active_max and int(last_active_max) > cutoff:
                out[str(uid)] = 'online'
            else:
                out[str(uid)] = 'AFK'
        for uid in user_ids:
            if uid not in found:
                out[str(uid)] = 'offline'
    return out
