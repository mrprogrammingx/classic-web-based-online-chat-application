"""DB package exports.

Expose init_db and provide a lazily-resolved DB attribute so callers
can import `from db import DB` and receive the DB path from
`core.config` at access time. This allows tests to update
AUTH_DB_PATH before importing modules that access `db.DB`.
"""
from .schema import init_db
import core.config as config


def __getattr__(name: str):
	if name == 'DB':
		return config.DB_PATH
	raise AttributeError(name)


__all__ = ["init_db", "DB"]
