const { test, expect } = require('./fixtures');
const helpers = require('./helpers');
const BASE = process.env.PLAYWRIGHT_BASE || 'http://127.0.0.1:8000';

// E2E: ensure UI edit and delete buttons work on the chat page
test.describe('chat UI edit/delete messages', () => {
  test('author can edit own message and then delete it via UI', async ({ browser, request }) => {
    // register two users (author and another)
    const { user: authorUser, token: authorToken } = await helpers.registerUser(request, 'ui-author');
    const { user: otherUser, token: otherToken } = await helpers.registerUser(request, 'ui-other');

    // create a public room as author
    const roomName = `UI EditDelete ${Date.now()}-${Math.random().toString(36).slice(2,6)}`;
    const rres = await request.post(`${BASE}/rooms`, { headers: { Authorization: `Bearer ${authorToken}`, 'Content-Type': 'application/json' }, data: { name: roomName, visibility: 'public' } });
    expect(rres.ok()).toBeTruthy(); const rb = await rres.json(); const room = rb.room; expect(room).toBeTruthy();

    // author posts a message via API so it appears in chat
    const msgRes = await request.post(`${BASE}/rooms/${room.id}/messages`, { headers: { Authorization: `Bearer ${authorToken}`, 'Content-Type': 'application/json' }, data: { text: 'original ui message' } });
    expect(msgRes.ok()).toBeTruthy(); const mb = await msgRes.json(); const msg = mb.message; expect(msg).toBeTruthy();

    // open browser as author and go to chat page for room
    const context = await browser.newContext({ viewport: { width: 1200, height: 900 } });
    await context.addCookies([{ name: 'token', value: authorToken, url: BASE, httpOnly: true, sameSite: 'Lax' }]);
    const page = await context.newPage();

    await page.goto(`${BASE}/static/chat/index.html?room=${room.id}`);

    // Override the page's showModal after navigation so our shim is used instead
    // of the default UI modal implementation (which doesn't expose the test save id).
    await page.evaluate(()=>{
      try{
        window.showModal = ((opts)=>{
          return new Promise((resolve)=>{
            try{
              const container = document.createElement('div');
              container.id = '__test_modal_container';
              container.style.position = 'fixed';
              container.style.left = '0';
              container.style.top = '0';
              container.style.zIndex = '99999';
              container.innerHTML = opts && opts.body ? opts.body : '';
              const save = document.createElement('button');
              save.textContent = opts && opts.confirmText ? opts.confirmText : 'OK';
              save.id = '__test_modal_save';
              // On click: resolve first, then remove the container shortly after
              save.addEventListener('click', ()=>{ try{ resolve(true); setTimeout(()=>{ try{ if(document.body.contains(container)) document.body.removeChild(container); }catch(e){} }, 100); }catch(e){ resolve(true); } });
              container.appendChild(save);
              document.body.appendChild(container);
            }catch(e){ resolve(true); }
          });
        });
      }catch(e){}
      try{ window.showToast = window.showToast || (()=>{}); }catch(e){}
    });

    // wait for messages container and the posted message to render
    await page.waitForSelector('#messages');
    // messages are rendered as elements with data-id attribute
    const messageSelector = `#messages .message[data-id="${msg.id}"]`;
    await page.waitForSelector(messageSelector, { timeout: 10000 });

    // Verify Edit button exists for author's message
    const editBtn = page.locator(messageSelector).locator('button.msg-edit');
    await expect(editBtn).toBeVisible({ timeout: 5000 });

  // Click edit, populate the textarea in the modal and confirm
  // Wait for the network request to the edit endpoint so we can capture its payload
  const editEndpoint = `/rooms/${room.id}/messages/${msg.id}/edit`;
  const waitReq = page.waitForRequest(request => request.url().endsWith(editEndpoint) && request.method() === 'POST');
  await editBtn.click();
  // modal textarea id used by messages.js is __edit_msg_input
  await page.waitForSelector('#__edit_msg_input', { timeout: 3000 });
  await page.fill('#__edit_msg_input', 'edited ui message');
  // click Save in the injected modal
  await page.click('#__test_modal_save');
  // capture the outgoing request and validate payload
  const req = await waitReq;
  let posted = null;
  try{ posted = JSON.parse(req.postData() || '{}'); }catch(e){}
  expect(posted && posted.text).toBe('edited ui message');

    // wait a moment and verify the message text updated in DOM
    await page.waitForTimeout(200); // allow client-side to update
    const bodyText = await page.locator(messageSelector).locator('.body').innerText();
    expect(bodyText.trim()).toBe('edited ui message');

    // Now verify Delete button exists and delete via UI
    const delBtn = page.locator(messageSelector).locator('button.msg-delete');
    await expect(delBtn).toBeVisible({ timeout: 5000 });
    await delBtn.click();
  // confirm modal Delete (target the test modal save button to avoid other 'Delete' buttons)
  await page.waitForSelector('#__test_modal_save', { timeout: 3000 });
  await page.click('#__test_modal_save');

    // Wait for message to be removed from DOM
    await page.waitForTimeout(200);
    const exists = await page.locator(messageSelector).count();
    expect(exists).toBe(0);

    await context.close();
  });
});
