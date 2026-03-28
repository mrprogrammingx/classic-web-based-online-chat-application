import uuid
import time


def _reg_and_token(client, prefix='u'):
    suffix = str(uuid.uuid4())[:8]
    email = f'{prefix}_{suffix}@example.com'
    username = f'{prefix}_{suffix}'
    r = client.post('/register', json={'email': email, 'username': username, 'password': 'pw'})
    assert r.status_code == 200
    return r.json()['user'], r.json()['token']


def test_room_messages_include_attached_files(client):
    s = client
    # register and create a public room
    u, tok = _reg_and_token(s, 'mf')
    headers = {'Authorization': f'Bearer {tok}'}
    r = s.post('/rooms', headers=headers, json={'name': f'msgfiles-{int(time.time())}', 'visibility': 'public'})
    assert r.status_code == 200
    room = r.json()['room']
    room_id = room['id']

    # post a message with a small file attachment
    s.s.headers.update({'Authorization': f'Bearer {tok}'})
    files = {'file': ('pic.png', b'fakepngcontent')}
    data = {'text': 'here is a pic'}
    r = s.post(f'/rooms/{room_id}/messages_with_file', headers=headers, files=files, data=data)
    assert r.status_code == 200

    # fetch messages and ensure the uploaded file appears on the message
    r = s.get(f'/rooms/{room_id}/messages', headers=headers)
    assert r.status_code == 200
    msgs = r.json().get('messages', [])
    # debug: print messages to help diagnose missing files
    print('DEBUG MESSAGES:', msgs)
    found = False
    for m in msgs:
        if m.get('text') == 'here is a pic':
            files_arr = m.get('files', [])
            # message should include at least one file
            assert isinstance(files_arr, list)
            assert len(files_arr) >= 1
            f0 = files_arr[0]
            # basic metadata present
            assert 'url' in f0 and '/rooms/' in f0['url']
            assert 'original_filename' in f0
            found = True
            break
    assert found
