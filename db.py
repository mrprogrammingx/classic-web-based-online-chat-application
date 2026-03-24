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
            description TEXT,
            visibility TEXT DEFAULT 'public',
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

        CREATE TABLE IF NOT EXISTS room_admins (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            room_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            created_at INTEGER,
            FOREIGN KEY(room_id) REFERENCES rooms(id) ON DELETE CASCADE,
            FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE,
            UNIQUE(room_id, user_id)
        );

        CREATE TABLE IF NOT EXISTS room_bans (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            room_id INTEGER NOT NULL,
            banned_id INTEGER NOT NULL,
            banner_id INTEGER,
            created_at INTEGER,
            FOREIGN KEY(room_id) REFERENCES rooms(id) ON DELETE CASCADE,
            FOREIGN KEY(banned_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY(banner_id) REFERENCES users(id) ON DELETE SET NULL,
            UNIQUE(room_id, banned_id)
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
        # ensure room names are unique at the DB level
        try:
            await db.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_rooms_name_unique ON rooms(name);")
            await db.commit()
        except Exception:
            # ignore if create index fails for any reason (older DBs etc.)
            pass
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
        # create friends table if missing
        await db.executescript('''
        CREATE TABLE IF NOT EXISTS friends (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            friend_id INTEGER NOT NULL,
            created_at INTEGER,
            FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY(friend_id) REFERENCES users(id) ON DELETE CASCADE,
            UNIQUE(user_id, friend_id)
        );
        ''')
        await db.commit()
        # create friend_requests and bans tables if missing
        await db.executescript('''
        CREATE TABLE IF NOT EXISTS friend_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            from_id INTEGER NOT NULL,
            to_id INTEGER NOT NULL,
            message TEXT,
            status TEXT NOT NULL DEFAULT 'pending',
            created_at INTEGER,
            FOREIGN KEY(from_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY(to_id) REFERENCES users(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS bans (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            banner_id INTEGER NOT NULL,
            banned_id INTEGER NOT NULL,
            created_at INTEGER,
            FOREIGN KEY(banner_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY(banned_id) REFERENCES users(id) ON DELETE CASCADE,
            UNIQUE(banner_id, banned_id)
        );
        ''')
        await db.commit()
        # migrate older rooms table to add description/visibility if missing
        cur = await db.execute("PRAGMA table_info('rooms')")
        cols = await cur.fetchall()
        existing_rooms_cols = {c[1] for c in cols}
        room_alters = []
        if 'description' not in existing_rooms_cols:
            room_alters.append("ALTER TABLE rooms ADD COLUMN description TEXT")
        if 'visibility' not in existing_rooms_cols:
            # default to public for older rows
            room_alters.append("ALTER TABLE rooms ADD COLUMN visibility TEXT DEFAULT 'public'")
        for stmt in room_alters:
            try:
                await db.execute(stmt)
            except Exception:
                pass
        if room_alters:
            await db.commit()
        # create private_messages table for 1:1 messages
        await db.executescript('''
        CREATE TABLE IF NOT EXISTS private_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            from_id INTEGER NOT NULL,
            to_id INTEGER NOT NULL,
            text TEXT,
            created_at INTEGER,
            FOREIGN KEY(from_id) REFERENCES users(id) ON DELETE SET NULL,
            FOREIGN KEY(to_id) REFERENCES users(id) ON DELETE SET NULL
        );
        ''')
        await db.commit()
        # create room_files table to track uploaded files for rooms
        await db.executescript('''
        CREATE TABLE IF NOT EXISTS room_files (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            room_id INTEGER NOT NULL,
            path TEXT NOT NULL,
            created_at INTEGER,
            FOREIGN KEY(room_id) REFERENCES rooms(id) ON DELETE CASCADE
        );
        ''')
        await db.commit()
        # create invitations table for private room invites
        await db.executescript('''
        CREATE TABLE IF NOT EXISTS invitations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            room_id INTEGER NOT NULL,
            inviter_id INTEGER NOT NULL,
            invitee_id INTEGER NOT NULL,
            created_at INTEGER,
            FOREIGN KEY(room_id) REFERENCES rooms(id) ON DELETE CASCADE,
            FOREIGN KEY(inviter_id) REFERENCES users(id) ON DELETE SET NULL,
            FOREIGN KEY(invitee_id) REFERENCES users(id) ON DELETE CASCADE,
            UNIQUE(room_id, invitee_id)
        );
        ''')
        await db.commit()
        # migrate room_bans table to add banner_id if missing
        cur = await db.execute("PRAGMA table_info('room_bans')")
        cols = await cur.fetchall()
        existing_bans_cols = {c[1] for c in cols}
        if 'banner_id' not in existing_bans_cols:
            try:
                await db.execute("ALTER TABLE room_bans ADD COLUMN banner_id INTEGER")
                await db.commit()
            except Exception:
                # ignore failures on older DBs
                pass
