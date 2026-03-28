"""Compatibility shim: re-export core utility helpers.

Older modules import from `routers.utils`. New code should import from
`core.utils`. Keeping this shim avoids changing many import sites at once.
"""
from core.utils import (
    presence_online_seconds,
    hash_pw,
    verify_pw,
    create_token,
    verify_token,
    store_session,
    remove_session,
    session_exists,
    update_session_expiry,
    require_auth,
    list_sessions_for_user,
    remove_session_by_jti,
    touch_tab,
    remove_tab,
    get_presence_status,
    get_presence_statuses,
)

__all__ = [
    'presence_online_seconds',
    'hash_pw',
    'verify_pw',
    'create_token',
    'verify_token',
    'store_session',
    'remove_session',
    'session_exists',
    'update_session_expiry',
    'require_auth',
    'list_sessions_for_user',
    'remove_session_by_jti',
    'touch_tab',
    'remove_tab',
    'get_presence_status',
    'get_presence_statuses',
]
