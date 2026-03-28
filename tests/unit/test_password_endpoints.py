import os
import time
import uuid
import sqlite3
import json
from fastapi.testclient import TestClient
from routers.app import app
from core.config import DB_PATH


def unique_email(prefix='u'):
    return f"{prefix}+{uuid.uuid4().hex[:8]}@example.com"


def test_password_reset_request_and_token(monkeypatch, tmp_path):
    # ensure TEST_MODE to get token in response
    monkeypatch.setenv('TEST_MODE', '1')
    client = TestClient(app)
    email = unique_email('pw')
    username = 'u_' + uuid.uuid4().hex[:6]
    pw = 'OldPass123'
    r = client.post('/register', json={'email': email, 'username': username, 'password': pw})
    assert r.status_code == 200
    # request reset
    r2 = client.post('/password/reset-request', json={'email': email})
    assert r2.status_code == 200
    data = r2.json()
    assert data.get('ok') is True
    token = data.get('token')
    assert token
    # verify token exists in DB
    conn = sqlite3.connect(DB_PATH)
    try:
        cur = conn.cursor()
        cur.execute('SELECT user_id, expires_at FROM password_resets WHERE token = ?', (token,))
        row = cur.fetchone()
        assert row is not None
        assert int(row[1]) >= int(time.time())
    finally:
        conn.close()


def test_password_reset_with_token_updates_password(monkeypatch):
    monkeypatch.setenv('TEST_MODE', '1')
    client = TestClient(app)
    email = unique_email('pw2')
    username = 'u_' + uuid.uuid4().hex[:6]
    pw = 'StartPass!1'
    r = client.post('/register', json={'email': email, 'username': username, 'password': pw})
    assert r.status_code == 200
    # request reset and get token
    r2 = client.post('/password/reset-request', json={'email': email})
    assert r2.status_code == 200
    token = r2.json().get('token')
    assert token
    # perform reset
    newpw = 'NewPass!2'
    r3 = client.post('/password/reset', json={'token': token, 'password': newpw})
    assert r3.status_code == 200
    assert r3.json().get('ok') is True
    # try login with new password
    lc = TestClient(app)
    r4 = lc.post('/login', json={'email': email, 'password': newpw})
    assert r4.status_code == 200


def test_change_own_password_requires_current(monkeypatch):
    client = TestClient(app)
    email = unique_email('changepw')
    username = 'u_' + uuid.uuid4().hex[:6]
    pw = 'OrigPass123'
    r = client.post('/register', json={'email': email, 'username': username, 'password': pw})
    assert r.status_code == 200
    # logged-in client has cookie; attempt change with wrong current
    r_wrong = client.patch('/me/password', json={'current_password': 'nope', 'new_password': 'DoesntMatter'})
    assert r_wrong.status_code == 401
    # change with correct current
    r_ok = client.patch('/me/password', json={'current_password': pw, 'new_password': 'BrandNew1'})
    assert r_ok.status_code == 200
    # verify new password works for login
    c2 = TestClient(app)
    r_login = c2.post('/login', json={'email': email, 'password': 'BrandNew1'})
    assert r_login.status_code == 200


def test_delete_own_account(monkeypatch):
    client = TestClient(app)
    email = unique_email('del')
    username = 'u_' + uuid.uuid4().hex[:6]
    pw = 'DeleteMe123'
    r = client.post('/register', json={'email': email, 'username': username, 'password': pw})
    assert r.status_code == 200
    # delete account while authenticated (cookie present)
    r2 = client.delete('/me')
    assert r2.status_code == 200
    assert r2.json().get('ok') is True
    # ensure user row removed from DB
    import sqlite3
    conn = sqlite3.connect(DB_PATH)
    try:
        cur = conn.cursor()
        cur.execute('SELECT id FROM users WHERE email = ?', (email,))
        row = cur.fetchone()
        assert row is None
    finally:
        conn.close()
    # login should fail
    c2 = TestClient(app)
    r_login = c2.post('/login', json={'email': email, 'password': pw})
    assert r_login.status_code == 401
