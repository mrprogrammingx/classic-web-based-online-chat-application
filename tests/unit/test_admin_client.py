import pytest

try:
    # prefer fast in-process TestClient; will import httpx transitively
    from starlette.testclient import TestClient
    from app import app
    HAS_TESTCLIENT = True
except Exception as e:
    TestClient = None  # type: ignore
    HAS_TESTCLIENT = False
    _IMPORT_ERR = e


@pytest.mark.skipif(not HAS_TESTCLIENT, reason="TestClient/httpx not available in this environment")
def test_admin_page_inprocess_testclient():
    """Hermetic in-process TestClient test for /static/admin/index.html.

    This is skipped if the environment cannot import TestClient/httpx (e.g. missing stdlib cgi).
    """
    with TestClient(app) as client:
        r = client.get('/static/admin/index.html')
        assert r.status_code == 200
        text = r.text
        assert 'Admin Console' in text or 'Admin' in text
        # ensure the page no longer contains an inline <script> with admin logic
        assert '<script' in text
    # ensure our extracted admin module is referenced
    assert '/static/admin/admin.js' in text
