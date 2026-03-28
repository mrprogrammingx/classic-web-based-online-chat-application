import time
import jwt
from passlib.context import CryptContext
import aiosqlite
import logging
from db import DB
from fastapi import HTTPException, Request
from typing import List, Dict, Any, Optional
from core.config import JWT_SECRET, JWT_ALGO, PRESENCE_ONLINE_SECONDS
from pathlib import Path
from core.logging_setup import ensure_file_handler

pwd = CryptContext(schemes=['pbkdf2_sha256'], deprecated='auto')

# Logger for this module. Don't reconfigure logging if the application has already
# set up handlers (uvicorn/config may configure logging). For local dev/tests
# this will ensure INFO messages are visible when no handlers are present.
logger = logging.getLogger(__name__)
if not logging.getLogger().handlers:
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(name)s: %(message)s')

# Ensure this module's logger writes to server.log so background runs and test
# runners can inspect messages. Centralized in `core.logging_setup` so other
# modules can reuse the same behaviour.
ensure_file_handler(logger)


def presence_online_seconds() -> int:
    return int(PRESENCE_ONLINE_SECONDS)


def hash_pw(pw: str) -> str:
    return pwd.hash(pw)


def verify_pw(pw: str, h: str) -> bool:
    return pwd.verify(pw, h)


def create_token(payload: Dict[str, Any], exp_seconds: int = 3600*24*7) -> str:
    data = payload.copy()
    data['exp'] = int(time.time() + exp_seconds)
    if 'jti' in payload:
        data['jti'] = payload['jti']
    return jwt.encode(data, JWT_SECRET, algorithm=JWT_ALGO)


def verify_token(token: str) -> Dict[str, Any]:
    return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGO])


async def store_session(jti: str, user_id: int, expires_at: int, ip: Optional[str] = None, user_agent: Optional[str] = None, last_active: Optional[int] = None):
    async with aiosqlite.connect(DB) as db:
        await db.execute('INSERT INTO sessions (jti, user_id, created_at, expires_at, ip, user_agent, last_active) VALUES (?, ?, ?, ?, ?, ?, ?)',
                         (jti, user_id, int(time.time()), expires_at, ip, user_agent, last_active or int(time.time())))
        await db.commit()


async def remove_session(jti: str):
    async with aiosqlite.connect(DB) as db:
        await db.execute('DELETE FROM sessions WHERE jti = ?', (jti,))
        await db.commit()


async def session_exists(jti: str) -> bool:
    async with aiosqlite.connect(DB) as db:
        cur = await db.execute('SELECT jti FROM sessions WHERE jti = ?', (jti,))
        row = await cur.fetchone()
        return bool(row)


async def update_session_expiry(jti: str, expires_at: int):
    async with aiosqlite.connect(DB) as db:
        await db.execute('UPDATE sessions SET expires_at = ? WHERE jti = ?', (expires_at, jti))
        await db.commit()


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


async def touch_tab(tab_id: str, jti: str, user_id: int, ip: Optional[str] = None, user_agent: Optional[str] = None):
    now = int(time.time())
    async with aiosqlite.connect(DB) as db:
        try:
            await db.execute('INSERT INTO tab_presence (tab_id, jti, user_id, created_at, last_active, user_agent, ip) VALUES (?, ?, ?, ?, ?, ?, ?)',
                             (tab_id, jti, user_id, now, now, user_agent, ip))
            logger.info('touch_tab: inserted tab_presence tab_id=%s user_id=%s jti=%s', tab_id, user_id, jti)
        except aiosqlite.IntegrityError:
            # existing tab -> update last_active and client info
            await db.execute('UPDATE tab_presence SET last_active = ?, user_agent = ?, ip = ? WHERE tab_id = ?', (now, user_agent, ip, tab_id))
            logger.info('touch_tab: updated tab_presence tab_id=%s user_id=%s jti=%s last_active=%s', tab_id, user_id, jti, now)
        await db.commit()


async def remove_tab(tab_id: str):
    async with aiosqlite.connect(DB) as db:
        await db.execute('DELETE FROM tab_presence WHERE tab_id = ?', (tab_id,))
        await db.commit()


async def get_presence_status(user_id: int) -> str:
    cutoff = int(time.time()) - presence_online_seconds()
    async with aiosqlite.connect(DB) as db:
        cur = await db.execute('SELECT COUNT(*) FROM tab_presence WHERE user_id = ?', (user_id,))
        total = (await cur.fetchone())[0]
        if total == 0:
            # no tab_presence rows -> consider offline unless session activity indicates otherwise
            cur2 = await db.execute('SELECT MAX(last_active) FROM sessions WHERE user_id = ?', (user_id,))
            sess_last = (await cur2.fetchone())[0]
            if sess_last and int(sess_last) > cutoff:
                return 'online'
            return 'offline'
        cur = await db.execute('SELECT COUNT(*) FROM tab_presence WHERE user_id = ? AND last_active > ?', (user_id, cutoff))
        active = (await cur.fetchone())[0]
        logger.info("Calculating presence status for user %s with active: %d cutoff %d (current time %d)", user_id, active, cutoff, int(time.time()))

        if active > 0:
            return 'online'
        # No active tab, but possibly recent session activity
        cur3 = await db.execute('SELECT MAX(last_active) FROM sessions WHERE user_id = ?', (user_id,))
        sess_last2 = (await cur3.fetchone())[0]
        if sess_last2 and int(sess_last2) > cutoff:
            return 'online'
        return 'AFK'


async def get_presence_statuses(user_ids: list) -> Dict[str, str]:
    if not user_ids:
        return {}
    cutoff = int(time.time()) - presence_online_seconds()
    logger.info("Calculating presence statuses for users %s with cutoff %d (current time %d)", user_ids, cutoff, int(time.time()))
    placeholders = ','.join(['?'] * len(user_ids))
    sql = f"SELECT user_id, COUNT(*) as total, MAX(last_active) as last_active_max FROM tab_presence WHERE user_id IN ({placeholders}) GROUP BY user_id"
    params = list(user_ids)
    out: Dict[str, str] = {}
    async with aiosqlite.connect(DB) as db:
        cur = await db.execute(sql, tuple(params))
        rows = await cur.fetchall()
        found = set()
        # map of user_id -> max last_active from tab_presence
        tp_max = {}
        for r in rows:
            uid, total, last_active_max = r[0], r[1], r[2]
            found.add(uid)
            tp_max[uid] = int(last_active_max) if last_active_max is not None else None
            if total == 0:
                out[str(uid)] = 'offline'
            elif last_active_max and int(last_active_max) > cutoff:
                out[str(uid)] = 'online'
            else:
                out[str(uid)] = 'AFK'
        for uid in user_ids:
            if uid not in found:
                out[str(uid)] = 'offline'
        # For any user not already marked online, check sessions.last_active as a fallback
        # Build a list of users to check
        to_check = [int(u) for u, s in out.items() if s != 'online']
        if to_check:
            placeholders2 = ','.join(['?'] * len(to_check))
            sql2 = f"SELECT user_id, MAX(last_active) as sess_last FROM sessions WHERE user_id IN ({placeholders2}) GROUP BY user_id"
            cur2 = await db.execute(sql2, tuple(to_check))
            srows = await cur2.fetchall()
            for sr in srows:
                uid2, sess_last = sr[0], sr[1]
                if sess_last and int(sess_last) > cutoff:
                    out[str(uid2)] = 'online'
    return out
