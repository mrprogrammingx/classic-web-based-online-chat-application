const BASE = process.env.PLAYWRIGHT_BASE || 'http://127.0.0.1:8000';

async function registerUser(request, prefix){
  const suffix = Math.random().toString(36).slice(2,8);
  const email = `${prefix}_${suffix}@example.com`;
  const username = `${prefix}_${suffix}`;
  const resp = await request.post(`${BASE}/register`, { data: { email, username, password: 'pw' } });
  if(!resp.ok()) throw new Error('register failed: ' + resp.status());
  const body = await resp.json();
  return { user: body.user, token: body.token };
}

async function createPrivateRoomAndInvite(request, ownerToken, inviteeId){
  const roomResp = await request.post(`${BASE}/rooms`, {
    data: { name: `pw-room-${Date.now()}`, visibility: 'private' },
    headers: { Authorization: `Bearer ${ownerToken}` }
  });
  if(!roomResp.ok()) throw new Error('create room failed');
  const room = await roomResp.json();
  const roomId = room.room.id;
  const inv = await request.post(`${BASE}/rooms/${roomId}/invite`, { data: { invitee_id: inviteeId }, headers: { Authorization: `Bearer ${ownerToken}` } });
  if(!inv.ok()) throw new Error('invite failed');
  return { room: room.room };
}

module.exports = { registerUser, createPrivateRoomAndInvite };
