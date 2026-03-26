import requests
import pytest
from test_auth_admin import BASE, server_available


@pytest.mark.skipif(not server_available(), reason="server not running on localhost:8000")
def test_chat_page_header_and_admin_link():
    """Verify chat page references the moved header loader and admin link points to admin index."""
    r = requests.get(BASE + '/static/chat/index.html', timeout=5)
    assert r.status_code == 200
    text = r.text
    # header loader script should be present in the page
    assert '/static/header/header-loader.js' in text
    # the canonical admin href is published via site-config.js — verify it's available
    r2 = requests.get(BASE + '/static/site-config.js', timeout=5)
    assert r2.status_code == 200
    assert '/static/admin/index.html' in r2.text


@pytest.mark.skipif(not server_available(), reason="server not running on localhost:8000")
def test_app_js_contains_selectRoom():
    """Ensure the client JS defines selectRoom (prevents runtime ReferenceError).

    This checks the shipped JS source contains the function; it's a lightweight smoke test
    that doesn't require a full browser run.
    """
    r = requests.get(BASE + '/static/app.js', timeout=5)
    assert r.status_code == 200
    js = r.text
    assert 'function selectRoom' in js, 'selectRoom function not found in /static/app.js'
