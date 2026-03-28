from fastapi.testclient import TestClient
from routers.app import app
import uuid


def test_home_requires_auth_inprocess():
    client = TestClient(app)
    # TestClient follows redirects; assert a redirect happened and final URL is the login page
    r = client.get('/static/home.html')
    # ensure there was at least one redirect in the history
    assert getattr(r, 'history', [])
    # final URL should be the login page
    assert str(r.url).endswith('/static/auth/login.html')


def test_home_allows_authenticated_user_inprocess():
    client = TestClient(app)
    email = f'test+{uuid.uuid4().hex[:8]}@example.com'
    username = f'user_{uuid.uuid4().hex[:8]}'
    pw = 'pw1234'
    resp = client.post('/register', json={'email': email, 'username': username, 'password': pw})
    assert resp.status_code == 200
    # cookie should now be present in client; request home
    r2 = client.get('/static/home.html')
    assert r2.status_code == 200
    assert 'Home' in r2.text or '<div id="my-presence"' in r2.text
