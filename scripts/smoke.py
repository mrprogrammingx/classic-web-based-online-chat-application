import requests, random
BASE = 'http://127.0.0.1:8000'
u = f'user{random.randint(1000,9999)}@example.com'
data = {'email': u, 'username': u.split('@')[0], 'password': 'Secret123!'}
print('register', requests.post(BASE + '/register', json=data).json())
print('login', requests.post(BASE + '/login', json={'email': data['email'], 'password': data['password']}).json())
