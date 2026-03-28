const { test, expect } = require('./fixtures');
const BASE = process.env.PLAYWRIGHT_BASE || 'http://127.0.0.1:8000';

// End-to-end flow for room management: create owner/member, create room,
// promote member to admin, ban the member, unban them, and verify DB state
// via the public room endpoints.

test('rooms: promote -> ban -> unban end-to-end', async ({ browser }) => {
  const request = await require('playwright').request.newContext();

  // Create owner user
  const ownerResp = await request.post(`${BASE}/_test/create_user`, {
    headers: { 'Content-Type': 'application/json' },
    data: JSON.stringify({ email: `owner_${Date.now()}@example.com`, username: `owner_${Date.now()}`, password: 'pw' })
  });
  expect(ownerResp.ok()).toBeTruthy();
  const ownerBody = await ownerResp.json();
  const ownerToken = ownerBody && ownerBody.token;
  const ownerUser = ownerBody && ownerBody.user;
  expect(ownerToken).toBeTruthy();

  // Create member user
  const memberResp = await request.post(`${BASE}/_test/create_user`, {
    headers: { 'Content-Type': 'application/json' },
    data: JSON.stringify({ email: `member_${Date.now()}@example.com`, username: `member_${Date.now()}`, password: 'pw' })
  });
  expect(memberResp.ok()).toBeTruthy();
  const memberBody = await memberResp.json();
  const memberToken = memberBody && memberBody.token;
  const memberUser = memberBody && memberBody.user;
  expect(memberToken).toBeTruthy();

  // Owner creates a public room
  const roomName = `room_manage_${Date.now()}`;
  const createRoomResp = await request.post(`${BASE}/rooms`, {
    headers: { Authorization: `Bearer ${ownerToken}`, 'Content-Type': 'application/json' },
    data: JSON.stringify({ name: roomName, description: 'E2E manage room', visibility: 'public' })
  });
  expect(createRoomResp.ok()).toBeTruthy();
  const roomBody = await createRoomResp.json();
  const room = roomBody && roomBody.room;
  expect(room).toBeTruthy();
  const roomId = room.id;

  // Member joins the public room
  const joinResp = await request.post(`${BASE}/rooms/${roomId}/join`, {
    headers: { Authorization: `Bearer ${memberToken}`, 'Content-Type': 'application/json' }
  });
  expect(joinResp.ok()).toBeTruthy();

  // Owner promotes member to admin
  const promoteResp = await request.post(`${BASE}/rooms/${roomId}/admins/add`, {
    headers: { Authorization: `Bearer ${ownerToken}`, 'Content-Type': 'application/json' },
    data: JSON.stringify({ user_id: memberUser.id })
  });
  expect(promoteResp.ok()).toBeTruthy();

  // Verify via GET /rooms/{id} that member is in admins
  const getAfterPromote = await request.get(`${BASE}/rooms/${roomId}`, {
    headers: { Authorization: `Bearer ${ownerToken}` }
  });
  expect(getAfterPromote.ok()).toBeTruthy();
  const gaBody = await getAfterPromote.json();
  const gaRoom = gaBody && gaBody.room;
  expect(gaRoom.admins).toContain(memberUser.id);

  // Owner bans the member
  const banResp = await request.post(`${BASE}/rooms/${roomId}/ban`, {
    headers: { Authorization: `Bearer ${ownerToken}`, 'Content-Type': 'application/json' },
    data: JSON.stringify({ user_id: memberUser.id })
  });
  expect(banResp.ok()).toBeTruthy();

  // After ban, GET /rooms/{id} should not list the member in members/admins, but bans should include them
  const getAfterBan = await request.get(`${BASE}/rooms/${roomId}`, { headers: { Authorization: `Bearer ${ownerToken}` } });
  expect(getAfterBan.ok()).toBeTruthy();
  const gbBody = await getAfterBan.json();
  const gbRoom = gbBody && gbBody.room;
  expect(gbRoom.members).not.toContain(memberUser.id);
  expect(gbRoom.admins).not.toContain(memberUser.id);
  expect(gbRoom.bans).toContain(memberUser.id);

  // Owner unbans the member
  const unbanResp = await request.post(`${BASE}/rooms/${roomId}/unban`, {
    headers: { Authorization: `Bearer ${ownerToken}`, 'Content-Type': 'application/json' },
    data: JSON.stringify({ user_id: memberUser.id })
  });
  expect(unbanResp.ok()).toBeTruthy();

  // After unban, GET /rooms/{id} should not include the user in bans
  const getAfterUnban = await request.get(`${BASE}/rooms/${roomId}`, { headers: { Authorization: `Bearer ${ownerToken}` } });
  expect(getAfterUnban.ok()).toBeTruthy();
  const guBody = await getAfterUnban.json();
  const guRoom = guBody && guBody.room;
  expect(guRoom.bans).not.toContain(memberUser.id);

  // Member should now be able to join again
  const joinAfterUnban = await request.post(`${BASE}/rooms/${roomId}/join`, {
    headers: { Authorization: `Bearer ${memberToken}`, 'Content-Type': 'application/json' }
  });
  expect(joinAfterUnban.ok()).toBeTruthy();

  // Cleanup: owner deletes the room
  const delResp = await request.delete(`${BASE}/rooms/${roomId}`, { headers: { Authorization: `Bearer ${ownerToken}` } });
  expect(delResp.ok()).toBeTruthy();

});
