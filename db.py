import aiosqlite
DB = 'auth.db'

async def init_db():
    async with aiosqlite.connect(DB) as db:
        await db.executescript('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            created_at INTEGER NOT NULL
        );

        CREATE TABLE IF NOT EXISTS rooms (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            owner_id INTEGER,
            name TEXT,
            created_at INTEGER,
            FOREIGN KEY(owner_id) REFERENCES users(id) ON DELETE SET NULL
        );

        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            room_id INTEGER,
            user_id INTEGER,
            text TEXT,
            created_at INTEGER,
            FOREIGN KEY(room_id) REFERENCES rooms(id) ON DELETE CASCADE,
            FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE SET NULL
        );

        CREATE TABLE IF NOT EXISTS memberships (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            room_id INTEGER,
            user_id INTEGER,
            created_at INTEGER,
            FOREIGN KEY(room_id) REFERENCES rooms(id) ON DELETE CASCADE,
            FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS sessions (
            jti TEXT PRIMARY KEY,
            user_id INTEGER NOT NULL,
            created_at INTEGER NOT NULL,
            expires_at INTEGER NOT NULL,
            ip TEXT,
            user_agent TEXT,
            last_active INTEGER,
            FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS tab_presence (
            tab_id TEXT PRIMARY KEY,
            jti TEXT NOT NULL,
            user_id INTEGER NOT NULL,
            created_at INTEGER NOT NULL,
            last_active INTEGER NOT NULL,
            user_agent TEXT,
            ip TEXT,
            FOREIGN KEY(jti) REFERENCES sessions(jti) ON DELETE CASCADE,
            FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
        );
        ''')
        await db.commit()
        # run migrations for existing DB: add columns to sessions if missing
        cur = await db.execute("PRAGMA table_info('sessions')")
        cols = await cur.fetchall()
        existing = {c[1] for c in cols}
        alters = []
        if 'ip' not in existing:
            alters.append("ALTER TABLE sessions ADD COLUMN ip TEXT")
        if 'user_agent' not in existing:
            alters.append("ALTER TABLE sessions ADD COLUMN user_agent TEXT")
        if 'last_active' not in existing:
            alters.append("ALTER TABLE sessions ADD COLUMN last_active INTEGER")
        for stmt in alters:
            try:
                await db.execute(stmt)
            except Exception:
                # ignore if alter fails for any reason
                pass
        if alters:
            await db.commit()
        # add is_admin to users if missing
        cur = await db.execute("PRAGMA table_info('users')")
        cols = await cur.fetchall()
        existing = {c[1] for c in cols}
        if 'is_admin' not in existing:
            try:
                await db.execute("ALTER TABLE users ADD COLUMN is_admin INTEGER DEFAULT 0")
                await db.commit()
            except Exception:
                pass
