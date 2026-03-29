"""DB package exports.

Provide `init_db` and a DB path proxy object that resolves the
configured database path at use time. Some modules import `DB` at
module-import time; exporting a small path-like proxy ensures those
modules still use the environment-overridden `AUTH_DB_PATH` when the
DB is actually opened.
"""
from .schema import init_db
import core.config as config
import os
import sys
import types


class _DBPathProxy:
	"""A tiny path-like proxy which resolves to the current
	`core.config.DB_PATH` whenever it's coerced to a filesystem path.

	This implements the ``__fspath__`` protocol and ``__str__`` so
	functions like ``aiosqlite.connect(DB)`` and ``sqlite3.connect(str(DB))``
	will pick up the latest value from environment-backed config.
	"""

	def __fspath__(self):
		# If tests or runtime set an explicit override, prefer it. This
		# supports test suites that assign `db.DB = '/tmp/x'` while still
		# allowing the normal env-backed `core.config.DB_PATH` resolution.
		mod = sys.modules.get(__name__)
		# module may be wrapped in a proxy; try to read internal override
		_override = getattr(mod, '_DB_OVERRIDE', None)
		if _override:
			return _override
		return config.DB_PATH

	def __str__(self):
		return config.DB_PATH

	def __repr__(self):
		return f"<DBPathProxy path={config.DB_PATH!r}>"


# Export a single DB object that behaves like a path. Modules that do
# ``from db import DB`` will receive this proxy and any subsequent
# resolution will call into core.config to get the current value.
DB = _DBPathProxy()

# Allow tests to set an explicit DB path by assigning to `db.DB`. Many
# existing tests do `db.DB = db_path`; replacing the name in the module
# would normally overwrite the proxy. To support that while keeping the
# proxy object authoritative, expose an internal override variable and
# replace the module with a small proxy that intercepts assignments to
# `DB` and stores the override instead of replacing the attribute.
_DB_OVERRIDE = None

__all__ = ["init_db", "DB"]


# Replace this module in sys.modules with a proxy that intercepts
# assignments to `DB` so tests that do `import db; db.DB = '...'` will
# set the internal override rather than clobbering the proxy object.
class _ModuleProxy(types.ModuleType):
	def __init__(self, mod):
		super().__init__(mod.__name__)
		# keep a reference to the original module object
		self._orig = mod

	def __getattr__(self, name):
		return getattr(self._orig, name)

	def __setattr__(self, name, value):
		# internal bookkeeping attributes go on the proxy itself
		if name in ('_orig', '__dict__'):
			return super().__setattr__(name, value)
		if name == 'DB':
			# set the internal override on the original module
			setattr(self._orig, '_DB_OVERRIDE', value)
			return
		setattr(self._orig, name, value)


# swap module entry in sys.modules
_orig_mod = sys.modules.get(__name__)
if not isinstance(_orig_mod, _ModuleProxy):
	sys.modules[__name__] = _ModuleProxy(_orig_mod)
