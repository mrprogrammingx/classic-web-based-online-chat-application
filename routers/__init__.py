"""Central router registration for the application.

This keeps `app.py` small and lets us manage router wiring from one place.
"""
from fastapi import FastAPI


def register_routers(app: FastAPI) -> None:
    # Import routers here to avoid circular imports at module import time
    from .presence import router as presence_router
    from .admin import router as admin_router
    from .friends import router as friends_router
    from .messages import router as messages_router
    from .rooms import router as rooms_router
    from .notifications import router as notifications_router
    from .users import router as users_router
    from .sessions import router as sessions_router

    app.include_router(presence_router)
    app.include_router(admin_router)
    app.include_router(friends_router)
    app.include_router(messages_router)
    app.include_router(rooms_router)
    app.include_router(notifications_router)
    app.include_router(users_router)
    app.include_router(sessions_router)
