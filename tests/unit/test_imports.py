import importlib
import pytest
from fastapi import FastAPI


MODULES = [
    "app",
    "routers.app",
    "routers.presence",
    "routers.messages",
    "routers.rooms",
    "routers.users",
    "routers.notifications",
    "routers.friends",
]


def test_import_app_module():
    """Ensure the top-level `app` module exists and exposes a FastAPI app instance.

    This prevents regressions where uvicorn can't import `app:app`.
    """
    m = importlib.import_module("app")
    assert hasattr(m, "app"), "module 'app' must expose 'app'"
    assert isinstance(m.app, FastAPI), "app.app must be a FastAPI instance"


@pytest.mark.parametrize("module_name", MODULES)
def test_import_router_modules(module_name):
    """Try importing each important module to catch ModuleNotFoundError / ImportError early.

    These modules previously used top-level `from utils import ...` and would fail when
    uvicorn tried to import `app:app`.
    """
    importlib.import_module(module_name)
