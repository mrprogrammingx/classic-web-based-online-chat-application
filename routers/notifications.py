from fastapi import APIRouter, Depends
import aiosqlite
import db as db_mod
from core.utils import require_auth

router = APIRouter()


@router.get('/notifications/unread-summary')
async def unread_summary(user=Depends(require_auth)):
    uid = user['id']
    async with aiosqlite.connect(db_mod.DB) as db:
        # rooms: count unread messages per room the user is a member of
        cur = await db.execute('''
            SELECT m.room_id, COUNT(*), r.name
            FROM messages msg
            JOIN memberships m ON m.room_id = msg.room_id
            LEFT JOIN rooms r ON r.id = m.room_id
            WHERE m.user_id = ? AND (m.last_read_at IS NULL OR msg.created_at > m.last_read_at)
            GROUP BY m.room_id
        ''', (uid,))
        rows = await cur.fetchall()
        rooms = [{'room_id': r[0], 'unread_count': r[1], 'room_name': r[2]} for r in rows]

        # dialogs: count unread private messages per sender
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

        # resolve display names for dialog partners
        other_ids = list(dialogs_map.keys())
        names_map = {}
        if other_ids:
            placeholders = ','.join(['?'] * len(other_ids))
            cur = await db.execute(f'SELECT id, username, email FROM users WHERE id IN ({placeholders})', tuple(other_ids))
            urows = await cur.fetchall()
            for ur in urows:
                names_map[ur[0]] = ur[1] or ur[2] or f'user{ur[0]}'

        dialogs = [{'other_id': k, 'unread_count': v, 'other_name': names_map.get(k, f'user{k}')} for k, v in dialogs_map.items()]
        return {'rooms': rooms, 'dialogs': dialogs}
