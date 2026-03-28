from fastapi import APIRouter, Depends
import aiosqlite
from db import DB
from core.utils import require_auth

router = APIRouter()


@router.get('/notifications/unread-summary')
async def unread_summary(user=Depends(require_auth)):
    uid = user['id']
    async with aiosqlite.connect(DB) as db:
        cur = await db.execute('''
            SELECT m.room_id, COUNT(*)
            FROM messages msg
            JOIN memberships m ON m.room_id = msg.room_id
            WHERE m.user_id = ? AND (m.last_read_at IS NULL OR msg.created_at > m.last_read_at)
            GROUP BY m.room_id
        ''', (uid,))
        rows = await cur.fetchall()
        rooms = [{'room_id': r[0], 'unread_count': r[1]} for r in rows]
        cur = await db.execute('''
            SELECT pm.from_id as other_id, COUNT(*)
            FROM private_messages pm
            JOIN dialog_reads dr ON dr.other_id = pm.from_id AND dr.user_id = ?
            WHERE pm.to_id = ? AND (dr.last_read_at IS NULL OR pm.created_at > dr.last_read_at)
            GROUP BY pm.from_id
        ''', (uid, uid))
        drows = await cur.fetchall()
        cur = await db.execute('''
            SELECT pm.from_id as other_id, COUNT(*)
            FROM private_messages pm
            WHERE pm.to_id = ? AND pm.from_id NOT IN (SELECT other_id FROM dialog_reads WHERE user_id = ?)
            GROUP BY pm.from_id
        ''', (uid, uid))
        drows2 = await cur.fetchall()
        dialogs_map = {}
        for r in drows:
            dialogs_map[r[0]] = r[1]
        for r in drows2:
            dialogs_map[r[0]] = dialogs_map.get(r[0], 0) + r[1]
        dialogs = [{'other_id': k, 'unread_count': v} for k, v in dialogs_map.items()]
        return {'rooms': rooms, 'dialogs': dialogs}
