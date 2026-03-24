from fastapi import APIRouter, Query, Depends
import aiosqlite
from db import DB
from utils import require_auth

router = APIRouter()

@router.get('/users')
async def get_users(ids: str = Query(None), user=Depends(require_auth)):
    """Lookup users by comma-separated ids. Returns { users: [ {id, username, email} ] }

    Requires authentication.
    """
    if not ids:
        return {'users': []}
    parts = [p.strip() for p in ids.split(',') if p.strip()]
    ids_int = []
    for p in parts:
        try:
            ids_int.append(int(p))
        except Exception:
            continue
    if not ids_int:
        return {'users': []}
    placeholders = ','.join(['?'] * len(ids_int))
    sql = f"SELECT id, username, email FROM users WHERE id IN ({placeholders})"
    async with aiosqlite.connect(DB) as db:
        cur = await db.execute(sql, tuple(ids_int))
        rows = await cur.fetchall()
        users = [{'id': r[0], 'username': r[1], 'email': r[2]} for r in rows]
        return {'users': users}
