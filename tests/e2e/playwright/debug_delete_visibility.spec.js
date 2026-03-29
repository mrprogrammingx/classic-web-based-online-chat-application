const { test, expect } = require('./fixtures');
const helpers = require('./helpers');
const BASE = process.env.PLAYWRIGHT_BASE || 'http://127.0.0.1:8000';

test.describe('debug delete button visibility', () => {
  test('anonymous cannot see delete button', async ({ browser, request }) => {
    // create an owner and a room via API so there's something to open
    const { user: ownerUser, token: ownerToken } = await helpers.registerUser(request, 'dbg-owner');
    const roomName = `DBGRoom ${Date.now()}-${Math.random().toString(36).slice(2,6)}`;
    let room = null;
    const createRes = await request.post(`${BASE}/_test/create_room`, { data: { name: roomName, description: 'debug', visibility: 'public', owner_id: ownerUser.id } }).catch(()=>null);
    if(createRes && createRes.ok()){
      const b = await createRes.json(); room = b && b.room;
    }
    if(!room){
      const r = await request.post(`${BASE}/rooms`, { headers: { 'Authorization': `Bearer ${ownerToken}`, 'Content-Type': 'application/json' }, data: { name: roomName, description: 'debug', visibility: 'public' } });
      expect(r.ok()).toBeTruthy(); const b = await r.json(); room = b.room;
    }
    expect(room).toBeTruthy();

    // Open browser context as anonymous (no cookies/token)
    const context = await browser.newContext({ viewport: { width: 1200, height: 900 } });
    const page = await context.newPage();
    await page.goto(`${BASE}/static/rooms/index.html`);

    // wait for the room to appear in the list
    await page.waitForSelector('#rooms-list');
    await page.waitForFunction((id) => !!document.querySelector(`#rooms-list li[data-id="${id}"]`), room.id, { timeout: 10000 });
    const li = page.locator(`#rooms-list li[data-id="${room.id}"]`);
    await expect(li).toBeVisible({ timeout: 10000 });

    // open details
    const anchor = li.locator('a').first();
    try{ await anchor.click({ timeout: 3000 }); }catch(e){ await page.evaluate((rid)=>{ try{ if(window && typeof window.selectRoom === 'function') window.selectRoom({ id: rid }); }catch(e){} }, room.id); }

    // ensure details visible
    const details = page.locator('#room-details');
    await expect(details).toBeVisible({ timeout: 5000 });

    // check computed style of delete button
    const display = await page.evaluate(()=>{
      const b = document.getElementById('btn-delete-room');
      if(!b) return null;
      return window.getComputedStyle(b).display;
    });
    console.log('delete button computed display:', display);
    // capture screenshot for debugging
    await page.screenshot({ path: 'test-results/debug-delete-anon.png', fullPage: false });

    expect(display).toBe('none');

    await context.close();
  });
});
