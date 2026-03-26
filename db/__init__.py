"""DB package exports.

Expose DB and init_db so other modules can continue to import
`from db import DB, init_db` while the schema/migration logic lives in
`db.schema`.
"""
from .schema import init_db, DB

__all__ = ["init_db", "DB"]
