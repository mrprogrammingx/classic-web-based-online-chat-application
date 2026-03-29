const { test, expect } = require('./fixtures');
const helpers = require('./helpers');
const BASE = process.env.PLAYWRIGHT_BASE || 'http://127.0.0.1:8000';

test.describe('rooms delete flow', () => {
  test('owner can see delete button and delete a room', async ({ browser, request }) => {
    // register owner
    const { user: ownerUser, token: ownerToken } = await helpers.registerUser(request, 'owner-delete');

    // create a room as owner via test endpoint if available
    const roomName = `DeleteRoom ${Date.now()}-${Math.random().toString(36).slice(2,6)}`;
    let room = null;
    const createRes = await request.post(`${BASE}/_test/create_room`, { data: { name: roomName, description: 'to be deleted', visibility: 'public', owner_id: ownerUser.id } }).catch(()=>null);
    if(createRes && createRes.ok()){
      const b = await createRes.json(); room = b && b.room;
    }
    if(!room){
      const r = await request.post(`${BASE}/rooms`, { headers: { 'Authorization': `Bearer ${ownerToken}`, 'Content-Type': 'application/json' }, data: { name: roomName, description: 'to be deleted', visibility: 'public' } });
      expect(r.ok()).toBeTruthy(); const b = await r.json(); room = b.room;
    }
    expect(room).toBeTruthy();

    // Open a browser context as owner and navigate to rooms index
    const context = await browser.newContext({ viewport: { width: 1200, height: 900 } });
    await context.addCookies([ { name: 'token', value: ownerToken, url: BASE, httpOnly: true, sameSite: 'Lax' } ]);
    const page = await context.newPage();
    await page.goto(`${BASE}/static/rooms/index.html`);

    // wait for room to show up in list
    await page.waitForSelector('#rooms-list');
    await page.waitForFunction((id) => !!document.querySelector(`#rooms-list li[data-id="${id}"]`), room.id, { timeout: 10000 });

    const li = page.locator(`#rooms-list li[data-id="${room.id}"]`);
    await expect(li).toBeVisible({ timeout: 10000 });

    // Click the room anchor to open details
    const anchor = li.locator('a').first();
    try{ await anchor.click({ timeout: 3000 }); }catch(e){ await page.evaluate((rid)=>{ try{ if(window && typeof window.selectRoom === 'function') window.selectRoom({ id: rid }); }catch(e){} }, room.id); }

    // Details panel should be visible and delete button present
    const details = page.locator('#room-details');
    await expect(details).toBeVisible({ timeout: 5000 });

    const deleteBtn = page.locator('#btn-delete-room');
    await expect(deleteBtn).toBeVisible();

    // Click delete and confirm via fallback confirm() (test harness may not have modal)
    await page.evaluate(()=>{ try{ window.showModal = window.showModal || (async ()=>true); }catch(e){} });
    await deleteBtn.click();

    // wait a bit and ensure the room is removed from the list
    await page.waitForTimeout(500);
    const still = await page.locator(`#rooms-list li[data-id="${room.id}"]`).count();
    expect(still).toBe(0);

    await context.close();
  });
});
