import time
import jwt
from passlib.context import CryptContext
import aiosqlite
from db import DB

pwd = CryptContext(schemes=['pbkdf2_sha256'], deprecated='auto')
JWT_SECRET = 'change_this_secret'
JWT_ALGO = 'HS256'

def hash_pw(pw: str) -> str:
    return pwd.hash(pw)

def verify_pw(pw: str, h: str) -> bool:
    return pwd.verify(pw, h)

def create_token(payload: dict, exp_seconds: int = 3600*24*7):
    data = payload.copy()
    data['exp'] = time.time() + exp_seconds
    # optional jti for session identification
    if 'jti' in payload:
        data['jti'] = payload['jti']
    return jwt.encode(data, JWT_SECRET, algorithm=JWT_ALGO)

async def store_session(jti: str, user_id: int, expires_at: int):
    async with aiosqlite.connect(DB) as db:
        await db.execute('INSERT INTO sessions (jti, user_id, created_at, expires_at) VALUES (?, ?, ?, ?)',
                         (jti, user_id, int(time.time()), expires_at))
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

def verify_token(token: str):
    return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGO])

async def get_user_by_email(email: str):
    async with aiosqlite.connect(DB) as db:
        cur = await db.execute('SELECT id, email, username, password FROM users WHERE email = ?', (email,))
        return await cur.fetchone()
