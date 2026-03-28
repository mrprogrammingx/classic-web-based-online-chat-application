from fastapi.testclient import TestClient
from routers.app import app


def test_missing_static_returns_404():
    client = TestClient(app)
    r = client.get('/static/does-not-exist.html')
    assert r.status_code == 404
    assert '404' in (r.text or '')


def test_missing_api_route_returns_404():
    client = TestClient(app)
    r = client.get('/api/no-such-endpoint')
    assert r.status_code == 404
    assert '404' in (r.text or '')
