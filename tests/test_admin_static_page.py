import requests
import pytest


@pytest.mark.usefixtures('server')
def test_admin_static_page_contains_admin_console_running_server():
    """
    Simple smoke test against a running dev server at http://127.0.0.1:8000.
    This avoids importing httpx/starlette TestClient which can fail in some envs.
    """
    url = "http://127.0.0.1:8000/static/admin/index.html"
    r = requests.get(url, timeout=5)
    assert r.status_code == 200
    text = r.text

    # Basic content checks
    assert "<h2>Admin Console</h2>" in text
    assert 'id="shared-header-placeholder"' in text
    assert 'id="modal-root"' in text and 'id="toast-root"' in text

    # Ensure page loads external admin module and does not include inline initAdminUI definition
    assert '<script type="module" src="/static/admin/admin.js"></script>' in text
    assert 'function initAdminUI' not in text

    # Ensure main.js/unread.js are included
    assert '<script src="/static/unread.js"></script>' in text
    assert '<script src="/static/main.js"></script>' in text
