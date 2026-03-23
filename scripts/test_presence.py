import requests
import time

BASE = 'http://127.0.0.1:8000'

# quick smoke: register, login, list sessions
u = 'testuser_presence@example.com'
print('registering...')
r = requests.post(BASE + '/register', json={'email': u, 'username': 'testpresence', 'password': 'Secret123!'})
print(r.status_code, r.text)
print('logging in...')
r = requests.post(BASE + '/login', json={'email': u, 'password': 'Secret123!'})
print(r.status_code, r.text)
if r.status_code == 200:
    token = r.json().get('token')
    jti = r.json().get('user') and r.json()['user'].get('id')
    headers = {'Authorization': f'Bearer {token}'}
    print('listing sessions...')
    s = requests.get(BASE + '/sessions', headers=headers)
    print(s.status_code, s.text)
    # create heartbeat
    print('sending heartbeat...')
    hb = requests.post(BASE + '/presence/heartbeat', headers=headers, json={'tab_id': 'tab-1', 'jti': s.json()['sessions'][0]['jti']})
    print(hb.status_code, hb.text)
    print('presence:', requests.get(BASE + f"/presence/{r.json()['user']['id']}").text)
else:
    print('login failed, abort')
