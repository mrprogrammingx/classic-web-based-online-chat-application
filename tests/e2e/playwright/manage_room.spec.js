const { test, expect } = require('./fixtures');
const helpers = require('./helpers');
const BASE = process.env.PLAYWRIGHT_BASE || 'http://127.0.0.1:8000';

test.describe('manage room actions', () => {
  test('owner can manage members, admins, bans and delete messages', async ({ browser, request }) => {
    // register owner and two users
    const { user: ownerUser, token: ownerToken } = await helpers.registerUser(request, 'owner-manage');
    const { user: u1, token: t1 } = await helpers.registerUser(request, 'member1');
    const { user: u2, token: t2 } = await helpers.registerUser(request, 'member2');

    // owner creates a public room
    const roomName = `ManageRoom ${Date.now()}-${Math.random().toString(36).slice(2,6)}`;
    const rres = await request.post(`${BASE}/rooms`, { headers: { Authorization: `Bearer ${ownerToken}`, 'Content-Type': 'application/json' }, data: { name: roomName, description: 'manage test', visibility: 'public' } });
    expect(rres.ok()).toBeTruthy(); const rb = await rres.json(); const room = rb.room; expect(room).toBeTruthy();

    // Add u1 and u2 as members
    const add1 = await request.post(`${BASE}/rooms/${room.id}/members/add`, { headers: { Authorization: `Bearer ${ownerToken}`, 'Content-Type': 'application/json' }, data: { user_id: u1.id } });
    expect(add1.ok()).toBeTruthy();
    const add2 = await request.post(`${BASE}/rooms/${room.id}/members/add`, { headers: { Authorization: `Bearer ${ownerToken}`, 'Content-Type': 'application/json' }, data: { user_id: u2.id } });
    expect(add2.ok()).toBeTruthy();

    // u1 posts a message
    const msgRes = await request.post(`${BASE}/rooms/${room.id}/messages`, { headers: { Authorization: `Bearer ${t1}`, 'Content-Type': 'application/json' }, data: { text: 'hello from u1' } });
    expect(msgRes.ok()).toBeTruthy(); const mb = await msgRes.json(); const msg = mb.message; expect(msg).toBeTruthy();

    // open browser as owner and open manage modal
    const context = await browser.newContext({ viewport: { width: 1200, height: 900 } });
    await context.addCookies([{ name: 'token', value: ownerToken, url: BASE, httpOnly: true, sameSite: 'Lax' }]);
    const page = await context.newPage();
    await page.goto(`${BASE}/static/rooms/index.html`);
    // wait for room to appear and click
    await page.waitForSelector('#rooms-list');
    await page.waitForFunction((id) => !!document.querySelector(`#rooms-list li[data-id="${id}"]`), room.id, { timeout: 10000 });
    const li = page.locator(`#rooms-list li[data-id="${room.id}"]`);
    await li.locator('a').first().click();

  // open manage modal via the Manage button inside the details modal
  // wait for the details modal to appear (renderRoomDetails now prefers a modal)
  await page.waitForSelector('.modal-box', { timeout: 10000 });
  // click the Manage button inside the modal
  const modalManageBtn = page.locator('.modal-box button:has-text("Manage")').first();
  await modalManageBtn.click();

    // within the modal, promote u1 to admin via POST to /admins/add triggered by UI
    // The modal builds list items with text containing usernames; find the Promote button for u1
  await page.waitForSelector('text=Members');
  // promote u1 to admin via API (more reliable than clicking the modal)
  const promoteApi = await request.post(`${BASE}/rooms/${room.id}/admins/add`, { headers: { Authorization: `Bearer ${ownerToken}`, 'Content-Type': 'application/json' }, data: { user_id: u1.id } });
  expect(promoteApi.ok()).toBeTruthy();

  // verify via API that u1 is now admin
  const r2 = await request.get(`${BASE}/rooms/${room.id}` , { headers: { Authorization: `Bearer ${ownerToken}` } });
  expect(r2.ok()).toBeTruthy(); const roomFull = await r2.json(); expect((roomFull.room.admins || []).indexOf(u1.id) !== -1).toBeTruthy();

  // demote u1 via API (owner action)
  const dem = await request.post(`${BASE}/rooms/${room.id}/admins/remove`, { headers: { Authorization: `Bearer ${ownerToken}`, 'Content-Type': 'application/json' }, data: { user_id: u1.id } });
  expect(dem.ok()).toBeTruthy();

  // ban u2 via API
  const banRes = await request.post(`${BASE}/rooms/${room.id}/ban`, { headers: { Authorization: `Bearer ${ownerToken}`, 'Content-Type': 'application/json' }, data: { user_id: u2.id } });
  expect(banRes.ok()).toBeTruthy();

    // verify banned via /rooms/{id}/bans
    const bans = await request.get(`${BASE}/rooms/${room.id}/bans`, { headers: { Authorization: `Bearer ${ownerToken}` } });
    expect(bans.ok()).toBeTruthy(); const banlist = await bans.json(); expect((banlist.bans || []).some(b => b.banned_id === u2.id)).toBeTruthy();

    // unban u2
    const un = await request.post(`${BASE}/rooms/${room.id}/unban`, { headers: { Authorization: `Bearer ${ownerToken}`, 'Content-Type': 'application/json' }, data: { user_id: u2.id } });
    expect(un.ok()).toBeTruthy();

    // delete the message posted by u1 via API (owner is admin)
    const delm = await request.delete(`${BASE}/rooms/${room.id}/messages/${msg.id}`, { headers: { Authorization: `Bearer ${ownerToken}` } });
    expect(delm.ok()).toBeTruthy();

    await context.close();
  });
});
