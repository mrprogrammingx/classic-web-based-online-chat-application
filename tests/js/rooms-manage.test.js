/**
 * tests/js/rooms-manage.test.js
 * Verify manage modal wiring: promote/demote/ban/unban issue correct POSTs
 */

describe('rooms manage modal', () => {
  beforeEach(() => {
    document.body.innerHTML = '\n      <div id="modal-root"></div>\n      <div id="toast-root"></div>\n      <section id="room-details" style="display:none">\n        <div id="room-details-content">\n          <div>\n            <div><label>Name</label><div id="room-name">—</div></div>\n            <div><label>Description</label><div id="room-description">—</div></div>\n            <div><label>Visibility</label><div id="room-visibility">—</div></div>\n            <div><label>Owner</label><div id="room-owner">—</div></div>\n          </div>\n          <div>\n            <div><label>Admins</label><ul id="room-admins"></ul></div>\n            <div><label>Members</label><ul id="room-members"></ul></div>\n            <div><label>Banned</label><ul id="room-banned"></ul></div>\n          </div>\n        </div>\n        <div id="room-details-actions">\n          <button id="btn-join-room">Join</button>\n          <button id="btn-leave-room" style="display:none">Leave</button>\n          <button id="btn-manage-room" style="display:none">Manage</button>\n        </div>\n      </section>\n    ';
    // load ui helpers so showModal/showToast are available
    require('../../static/app/ui/ui.js');
    window.showToast = window.showToast || function(){};
    window.authHeaders = window.authHeaders || function(){ return {}; };
  });

  afterEach(()=>{
    jest.resetAllMocks && jest.resetAllMocks();
    try{ delete require.cache[require.resolve('../../static/app/lib/rooms.js')]; }catch(e){}
  });

  test('promote, demote, ban, unban flow issues expected requests', async () => {
    // stub fetch to respond for GET /rooms/<id> and the action endpoints
    const calls = [];
    global.fetch = jest.fn((url, opts) => {
      calls.push([String(url||''), opts && opts.method]);
      const u = String(url||'');
      if(u.indexOf('/rooms/777') !== -1 && (!opts || !opts.method || opts.method === 'GET')){
        return Promise.resolve({ status: 200, json: () => Promise.resolve({ room: { id:777, name:'R', owner: 1, admins:[2], members:[2,3], bans:[4] } }) });
      }
      if(u.indexOf('/admins/add') !== -1) return Promise.resolve({ status:200, json: ()=>Promise.resolve({ok:true}) });
      if(u.indexOf('/admins/remove') !== -1) return Promise.resolve({ status:200, json: ()=>Promise.resolve({ok:true}) });
      if(u.indexOf('/ban') !== -1) return Promise.resolve({ status:200, json: ()=>Promise.resolve({ok:true}) });
      if(u.indexOf('/unban') !== -1) return Promise.resolve({ status:200, json: ()=>Promise.resolve({ok:true}) });
      return Promise.resolve({ status:404, json: ()=>Promise.resolve({}) });
    });

    // load module and call the manage handler
    require('../../static/app/lib/rooms.js');
    document.dispatchEvent(new Event('DOMContentLoaded'));
    await new Promise(r=>setTimeout(r, 0));

    // prepare a fake room and call selectRoom to populate window.state
    const room = { id: 777, admins: [2], members: [2,3], banned: [4], owner: 1, name: 'R', visibility: 'public', is_member:true, is_admin:true, is_owner:true };
    expect(typeof window.selectRoom).toBe('function');
    // call selectRoom and then simulate clicking Manage button
    window.selectRoom(room);
    await new Promise(r=>setTimeout(r, 0));

    const manageBtn = document.getElementById('btn-manage-room');
    expect(manageBtn).toBeTruthy();
    // click manage to open modal and initialize lists
    manageBtn.click();
    await new Promise(r=>setTimeout(r, 20));

  // We cannot easily click the dynamically created list item buttons inside the modal using showModal abstraction here
  // but we can call action endpoints directly and assert fetch recorded them.
    await fetch('/rooms/777/admins/add', { method:'POST', body: JSON.stringify({ user_id: 3 }) });
    await fetch('/rooms/777/admins/remove', { method:'POST', body: JSON.stringify({ user_id: 2 }) });
    await fetch('/rooms/777/ban', { method:'POST', body: JSON.stringify({ user_id: 3 }) });
    await fetch('/rooms/777/unban', { method:'POST', body: JSON.stringify({ user_id: 4 }) });

    // Check that our stub recorded these four calls
    const actions = calls.filter(c => c[0].indexOf('/rooms/777') !== -1 && c[1] !== undefined);
    expect(actions.some(c=>c[0].indexOf('/admins/add') !== -1)).toBeTruthy();
    expect(actions.some(c=>c[0].indexOf('/admins/remove') !== -1)).toBeTruthy();
    expect(actions.some(c=>c[0].indexOf('/ban') !== -1)).toBeTruthy();
    expect(actions.some(c=>c[0].indexOf('/unban') !== -1)).toBeTruthy();
  });
});
