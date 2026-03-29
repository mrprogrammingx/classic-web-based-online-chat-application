import time
import jwt
from passlib.context import CryptContext
import aiosqlite
import logging
import db as db_mod
DB = db_mod.DB
from fastapi import HTTPException, Request
from typing import List, Dict, Any, Optional
from core.config import JWT_SECRET, JWT_ALGO
import core.config as config
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
    # Evaluate the config value at call time so tests can change environment
    # variables prior to starting the server or calling presence helpers.
    return int(config.PRESENCE_ONLINE_SECONDS)


def afk_seconds() -> int:
    """AFK threshold: seconds of inactivity before a user with open tabs is AFK.
    Defaults to 60 (1 minute). Tests may override via AFK_SECONDS env var."""
    return int(config.AFK_SECONDS)


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
        # Do NOT default last_active to now — heartbeats should explicitly
        # set the session's last_active. Storing NULL here keeps newly
        # created sessions from being considered 'online' until activity
        # (heartbeat) occurs.
        await db.execute('INSERT INTO sessions (jti, user_id, created_at, expires_at, ip, user_agent, last_active) VALUES (?, ?, ?, ?, ?, ?, ?)',
                         (jti, user_id, int(time.time()), expires_at, ip, user_agent, last_active))
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


async def cleanup_stale_tabs(max_age_seconds: int = 86400):
    """Remove tab records that haven't been touched in max_age_seconds (default: 24 hours).
    
    This cleans up tab records from browsers that were closed without sending an
    explicit close signal. Called periodically during presence checks to keep the
    database clean and ensure users with all tabs closed show as 'offline'.
    """
    cutoff = int(time.time()) - max_age_seconds
    async with aiosqlite.connect(DB) as db:
        cur = await db.execute('SELECT COUNT(*) FROM tab_presence WHERE last_active < ?', (cutoff,))
        count = (await cur.fetchone())[0]
        if count > 0:
            await db.execute('DELETE FROM tab_presence WHERE last_active < ?', (cutoff,))
            await db.commit()
            logger.info('cleanup_stale_tabs: deleted %d stale tab records (older than %d seconds)', count, max_age_seconds)


async def get_presence_status(user_id: int) -> str:
    """Determine a single user's presence status.

    Rules:
      - **online**: at least one tab_presence row with last_active within
        the AFK threshold (user interacted recently).
      - **AFK**: tab_presence rows exist but ALL are older than the AFK
        threshold (user has tabs open but hasn't interacted).
      - **offline**: no tab_presence rows at all (no open tabs).
    """
    # Clean up stale tabs before checking presence
    await cleanup_stale_tabs()
    
    afk_cutoff = int(time.time()) - afk_seconds()
    async with aiosqlite.connect(DB) as db:
        # count total tabs and tabs that are active (within AFK window)
        cur = await db.execute('SELECT COUNT(*) FROM tab_presence WHERE user_id = ?', (user_id,))
        total = (await cur.fetchone())[0]
        if total == 0:
            return 'offline'
        cur = await db.execute('SELECT COUNT(*) FROM tab_presence WHERE user_id = ? AND last_active > ?', (user_id, afk_cutoff))
        active = (await cur.fetchone())[0]
        if active > 0:
            return 'online'
        return 'AFK'


async def get_presence_statuses(user_ids: list) -> Dict[str, str]:
    """Batch presence lookup for multiple users.

    Uses the same rules as get_presence_status:
      - Has tab with last_active within AFK threshold → online
      - Has tabs but all stale → AFK
      - No tabs → offline
    """
    if not user_ids:
        return {}
    
    # Clean up stale tabs before checking presence
    await cleanup_stale_tabs()
    
    afk_cutoff = int(time.time()) - afk_seconds()
    placeholders = ','.join(['?'] * len(user_ids))
    # For each user: total tab count AND count of tabs active within the AFK window
    sql = f"""
        SELECT user_id,
               COUNT(*) as total,
               SUM(CASE WHEN last_active > ? THEN 1 ELSE 0 END) as active_count
        FROM tab_presence
        WHERE user_id IN ({placeholders})
        GROUP BY user_id
    """
    params = [afk_cutoff] + list(user_ids)
    out: Dict[str, str] = {}
    async with aiosqlite.connect(DB) as db:
        cur = await db.execute(sql, tuple(params))
        rows = await cur.fetchall()
        found = set()
        for r in rows:
            uid, total, active_count = r[0], r[1], r[2] or 0
            found.add(uid)
            if total == 0:
                out[str(uid)] = 'offline'
            elif active_count > 0:
                out[str(uid)] = 'online'
            else:
                out[str(uid)] = 'AFK'
        # users with no tab_presence rows at all → offline
        for uid in user_ids:
            if uid not in found:
                out[str(uid)] = 'offline'
    return out
