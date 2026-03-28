from fastapi.testclient import TestClient
from routers.app import app

client = TestClient(app)
print('Cookies at start:', client.cookies.get_dict())
resp = client.get('/static/home.html')
print('Status code:', resp.status_code)
try:
    print('Final URL:', resp.url)
except Exception:
    print('Final URL not available on this Response object')
print('History length:', len(getattr(resp, 'history', [])))
print('Response headers:', resp.headers)
print('Response text head:')
print(resp.text[:400])
