"""Centralized logging helper used by modules to attach a FileHandler
that writes to ``server.log`` in the repository root.

Providing this as a tiny helper keeps per-module code small and makes the
behaviour easy to reuse and test.
"""
from pathlib import Path
import logging


def ensure_file_handler(logger: logging.Logger, filename: str = 'server.log', level: int = logging.INFO) -> None:
    """Ensure the given logger has a FileHandler writing to `filename` in
    the current working directory. This is safe to call multiple times; it
    will not add duplicate handlers for the same path.

    Any exceptions are swallowed so logging setup never crashes the app.
    """
    try:
        log_path = Path.cwd() / filename
        # Only add a FileHandler for this path if one doesn't already exist on this logger
        has_fh = False
        for h in logger.handlers:
            try:
                if isinstance(h, logging.FileHandler) and Path(getattr(h, 'baseFilename')).resolve() == log_path.resolve():
                    has_fh = True
                    break
            except Exception:
                continue
        if not has_fh:
            fh = logging.FileHandler(log_path, encoding='utf-8')
            fh.setLevel(level)
            fh.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(name)s: %(message)s'))
            logger.addHandler(fh)
    except Exception:
        # Fail silently — logging shouldn't crash the app
        pass
