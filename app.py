"""Top-level ASGI app wrapper so `uvicorn app:app` works from the project root.
This module simply re-exports the FastAPI ``app`` instance defined in ``routers.app``.
"""
from routers.app import app  # re-export the app instance

__all__ = ["app"]
