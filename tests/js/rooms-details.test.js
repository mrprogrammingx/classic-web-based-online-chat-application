/**
 * tests/js/rooms-details.test.js
 * Verify the Room Details panel is populated when window.selectRoom is called
 * and that join/leave/manage buttons reflect membership and role flags.
 */

describe('rooms details panel', () => {
  beforeEach(() => {
    // Minimal DOM required by renderRoomDetails
    document.body.innerHTML = `
      <div id="rooms-list"></div>
      <section id="room-details" style="display:none">
        <div id="room-details-content">
          <div>
            <div><label>Name</label><div id="room-name">—</div></div>
            <div><label>Description</label><div id="room-description">—</div></div>
            <div><label>Visibility</label><div id="room-visibility">—</div></div>
            <div><label>Owner</label><div id="room-owner">—</div></div>
          </div>
          <div>
            <div><label>Admins</label><ul id="room-admins"></ul></div>
            <div><label>Members</label><ul id="room-members"></ul></div>
            <div><label>Banned</label><ul id="room-banned"></ul></div>
          </div>
        </div>
        <div id="room-details-actions">
          <button id="btn-join-room">Join</button>
          <button id="btn-leave-room" style="display:none">Leave</button>
          <button id="btn-manage-room" style="display:none">Manage</button>
        </div>
      </section>
    `;
    // provide minimal globals used by the module
    window.showStatus = window.showStatus || function(){};
    window.showToast = window.showToast || function(){};
    window.authHeaders = window.authHeaders || function(){ return {}; };
  });

  afterEach(() => {
    jest.resetAllMocks && jest.resetAllMocks();
    // clear module cache so requiring rooms.js re-executes for each test
    try{ delete require.cache[require.resolve('../../static/app/lib/rooms.js')]; }catch(e){}
  });

  test('populates fields and lists when selectRoom is called (non-member)', async () => {
    require('../../static/app/lib/rooms.js');
    // construct a room object like the server might return
    const room = {
      id: 11,
      name: 'Test Room',
      description: 'A room for testing',
      visibility: 'public',
      owner: { display_name: 'OwnerUser' },
      admins: [{ display_name: 'Admin1' }, { display_name: 'Admin2' }],
      members: [{ display_name: 'Member1' }],
      banned: [],
      is_member: false,
      is_admin: false,
      is_owner: false
    };

    // call the exposed selectRoom to render details
    expect(typeof window.selectRoom).toBe('function');
    window.selectRoom(room);

    // allow DOM sync
    await new Promise(resolve => setTimeout(resolve, 0));

    const panel = document.getElementById('room-details');
    expect(panel.style.display).toBe('block');
    expect(document.getElementById('room-name').textContent).toBe('Test Room');
    expect(document.getElementById('room-description').textContent).toBe('A room for testing');
    expect(document.getElementById('room-visibility').textContent).toBe('public');
    expect(document.getElementById('room-owner').textContent).toBe('OwnerUser');

    const admins = document.querySelectorAll('#room-admins li');
    expect(admins.length).toBe(2);
    expect(admins[0].textContent).toBe('Admin1');

    const members = document.querySelectorAll('#room-members li');
    expect(members.length).toBe(1);
    expect(members[0].textContent).toBe('Member1');

    // Buttons: non-member => Join visible, Leave hidden, Manage hidden
    const joinBtn = document.getElementById('btn-join-room');
    const leaveBtn = document.getElementById('btn-leave-room');
    const manageBtn = document.getElementById('btn-manage-room');
    expect(joinBtn.style.display === '' || joinBtn.style.display === 'inline-flex').toBeTruthy();
    expect(leaveBtn.style.display === 'none').toBeTruthy();
    expect(manageBtn.style.display === 'none').toBeTruthy();
  });

  test('shows leave and manage when member and owner/admin', async () => {
    require('../../static/app/lib/rooms.js');
    const room = {
      id: 22,
      name: 'Admin Room',
      description: 'Owned room',
      visibility: 'private',
      owner: { name: 'OwnerX' },
      admins: [{ name: 'OwnerX' }],
      members: [{ name: 'OwnerX' }, { name: 'MemberA' }],
      banned: [{ name: 'BadActor' }],
      is_member: true,
      is_admin: true,
      is_owner: true
    };

    window.selectRoom(room);
    await new Promise(resolve => setTimeout(resolve, 0));

    expect(document.getElementById('room-name').textContent).toBe('Admin Room');
    expect(document.getElementById('room-visibility').textContent).toBe('private');
    const banned = document.querySelectorAll('#room-banned li');
    expect(banned.length).toBe(1);
    expect(banned[0].textContent).toBe('BadActor');

    const joinBtn = document.getElementById('btn-join-room');
    const leaveBtn = document.getElementById('btn-leave-room');
    const manageBtn = document.getElementById('btn-manage-room');
    // member -> leave visible, join hidden
    expect(leaveBtn.style.display === '' || leaveBtn.style.display === 'inline-flex').toBeTruthy();
    expect(joinBtn.style.display === 'none').toBeTruthy();
    // owner/admin -> manage visible
    expect(manageBtn.style.display === '' || manageBtn.style.display === 'inline-flex').toBeTruthy();
  });
});
