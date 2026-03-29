// Room Invitations UI
// Handles:
//   • "Invite" button for owners/admins of private rooms (members section)
//   • Accept/Decline buttons in the join-bar when the user has a pending invite
//   • "Pending Invitations" sidebar section for users who have been invited
(function(){

  // ── helpers ────────────────────────────────────────────────────────────────

  function escapeHtml(s){ return String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c])); }

  async function api(url, opts){
    try{
      if(typeof window.fetchJSON === 'function') return await window.fetchJSON(url, opts);
      opts = opts || {}; opts.credentials = 'include'; opts.headers = opts.headers || {};
      const r = await fetch(url, opts);
      return r.ok ? (await r.json().catch(()=>null)) : null;
    }catch(e){ return null; }
  }

  function toast(msg, type){ try{ window.showToast && window.showToast(msg, type||'success', 3000); }catch(e){} }

  // ── invite button in members section ──────────────────────────────────────

  /**
   * Inject an "Invite" button into the members section header if the current
   * user is owner/admin of a private room.  Call this each time a room is
   * selected (window.onRoomSelected hook or polled via custom event).
   */
  function refreshInviteButton(room){
    try{
      const membersHeader = document.querySelector('.members h3');
      if(!membersHeader) return;
      // remove existing invite button
      const existing = membersHeader.querySelector('.btn-invite-user');
      if(existing) existing.remove();

      if(!room) return;
      // only show for private rooms where the current user is owner or admin
      const isPrivate = room.visibility === 'private';
      const isOwner   = room.is_owner === true || (room.owner_id && String(room.owner_id) === String(window.__ME_ID));
      const isAdmin   = room.is_admin === true
        || (Array.isArray(room.admins) && room.admins.map(String).indexOf(String(window.__ME_ID)) !== -1);
      if(!isPrivate || (!isOwner && !isAdmin)) return;

      const btn = document.createElement('button');
      btn.className = 'btn-invite-user';
      btn.type = 'button';
      btn.title = 'Invite a user to this room';
      btn.textContent = '+ Invite';
      btn.addEventListener('click', () => openInviteModal(room));
      membersHeader.appendChild(btn);
    }catch(e){}
  }

  // ── invite modal ───────────────────────────────────────────────────────────

  async function openInviteModal(room){
    if(!window.showModal) return;
    // build modal body with a search input + results list
    const bodyEl = document.createElement('div');
    bodyEl.innerHTML = `
      <p class="invite-modal-desc">Search for a user to invite to <strong>${escapeHtml(room.name || 'this room')}</strong>.</p>
      <div class="invite-search-row">
        <input id="invite-user-search" type="text" class="invite-search-input" placeholder="Username or email…" autocomplete="off" />
        <button type="button" id="invite-search-btn" class="btn-search">Search</button>
      </div>
      <ul id="invite-search-results" class="invite-results" aria-live="polite"></ul>
      <p id="invite-status" class="invite-status" aria-live="polite"></p>
    `;

    // We use html:true so the DOM nodes are real
    const confirmed = await window.showModal({
      title: 'Invite to Room',
      body: bodyEl,
      html: true,
      confirmText: 'Done',
      cancelText: 'Cancel',
    });

    // Nothing to do on confirm — invites were sent via the search results buttons
    void confirmed;
  }

  // Wire up the search input inside #modal-root after showModal renders it.
  // We use event delegation on #modal-root so it works regardless of timing.
  (function wireInviteSearch(){
    try{
      const root = document.getElementById('modal-root') ||
        (function(){ const r=document.createElement('div'); r.id='modal-root'; document.body.appendChild(r); return r; })();

      root.addEventListener('click', async (e)=>{
        // Search button
        if(e.target && e.target.id === 'invite-search-btn'){
          await runInviteSearch();
          return;
        }
        // "Send Invite" result button
        if(e.target && e.target.classList.contains('btn-send-invite')){
          const btn = e.target;
          const userId = btn.dataset.userId;
          const roomId = btn.dataset.roomId;
          if(!userId || !roomId) return;
          btn.disabled = true;
          btn.textContent = 'Sending…';
          const res = await api(`/rooms/${roomId}/invite`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ invitee_id: Number(userId) }),
          });
          if(res && (res.ok || res.id)){
            btn.textContent = 'Invited ✓';
            toast('Invitation sent!', 'success');
          } else {
            btn.textContent = 'Send Invite';
            btn.disabled = false;
            toast('Failed to send invite', 'error');
          }
        }
      });

      root.addEventListener('keydown', async (e)=>{
        if(e.key === 'Enter' && e.target && e.target.id === 'invite-user-search'){
          e.preventDefault();
          await runInviteSearch();
        }
      });
    }catch(e){}
  })();

  async function runInviteSearch(){
    try{
      const input   = document.getElementById('invite-user-search');
      const list    = document.getElementById('invite-search-results');
      const status  = document.getElementById('invite-status');
      if(!input || !list) return;
      const q = (input.value || '').trim();
      if(!q){ if(status) status.textContent = 'Enter a username or email to search.'; return; }
      if(status) status.textContent = 'Searching…';
      list.innerHTML = '';
      const data = await api(`/users/search?q=${encodeURIComponent(q)}&limit=10`);
      const users = (data && data.users) || [];
      if(status) status.textContent = '';
      if(users.length === 0){
        const li = document.createElement('li'); li.className = 'invite-no-results';
        li.textContent = 'No users found.'; list.appendChild(li); return;
      }
      // get current room id from currentRoom
      const roomId = (window.currentRoom && window.currentRoom.id) ? window.currentRoom.id : null;
      if(!roomId){ if(status) status.textContent = 'No room selected.'; return; }
      users.forEach(u=>{
        const li = document.createElement('li'); li.className = 'invite-result-item';
        const name = escapeHtml(u.username || u.email || ('user'+u.id));
        li.innerHTML = `<span class="invite-result-name">${name}</span>
          <button type="button" class="btn-send-invite" data-user-id="${escapeHtml(String(u.id))}" data-room-id="${escapeHtml(String(roomId))}">Send Invite</button>`;
        list.appendChild(li);
      });
    }catch(e){ console.warn('invite search error', e); }
  }

  // ── join-bar: accept/decline for pending invites ──────────────────────────

  /**
   * Called by selectRoom (via the window.onInvitationsRefresh hook below).
   * Checks if the current user has a pending invitation to this room and if
   * so swaps the generic join-bar for accept/decline buttons.
   */
  async function refreshJoinBarForInvite(room){
    try{
      const joinBarEl  = document.getElementById('join-bar');
      if(!joinBarEl || joinBarEl.style.display === 'none') return;
      // only relevant for private rooms (public rooms use regular join)
      if(!room || room.visibility !== 'private') return;

      const data = await api(`/rooms/${room.id}/invites`);
      const invites = (data && data.invites) || [];
      // invites returned for non-admins are for the current user
      if(invites.length === 0) return;
      const invite = invites[0]; // take the first pending invite

      // replace join-bar content with accept/decline
      joinBarEl.innerHTML = '';
      const textEl = document.createElement('span');
      textEl.className = 'join-bar-text';
      textEl.textContent = 'You have been invited to this private room.';
      const acceptBtn = document.createElement('button');
      acceptBtn.type = 'button';
      acceptBtn.className = 'btn-join btn-accept-invite';
      acceptBtn.textContent = 'Accept';
      const declineBtn = document.createElement('button');
      declineBtn.type = 'button';
      declineBtn.className = 'btn-decline-invite';
      declineBtn.textContent = 'Decline';
      joinBarEl.appendChild(textEl);
      joinBarEl.appendChild(acceptBtn);
      joinBarEl.appendChild(declineBtn);

      acceptBtn.addEventListener('click', async ()=>{
        acceptBtn.disabled = true; acceptBtn.textContent = 'Joining…';
        const res = await api(`/rooms/${room.id}/invites/${invite.id}/accept`, { method: 'POST', headers: { 'Content-Type': 'application/json' } });
        if(res && res.ok){
          toast('You joined the room!', 'success');
          // refresh room and re-select
          const updated = await api(`/rooms/${encodeURIComponent(room.id)}`);
          const freshRoom = (updated && updated.room) ? updated.room : Object.assign({}, room, { is_member: true });
          if(window.rooms){
            const idx = window.rooms.findIndex(r => String(r.id) === String(room.id));
            if(idx !== -1) window.rooms[idx] = freshRoom; else window.rooms.unshift(freshRoom);
          }
          try{ if(typeof window.renderRooms === 'function') window.renderRooms(); }catch(e){}
          try{ if(typeof window.selectRoom === 'function') window.selectRoom(freshRoom); }catch(e){}
          loadPendingInvitations();
        } else {
          toast('Could not accept invite', 'error');
          acceptBtn.disabled = false; acceptBtn.textContent = 'Accept';
        }
      });

      declineBtn.addEventListener('click', async ()=>{
        declineBtn.disabled = true; declineBtn.textContent = 'Declining…';
        const res = await api(`/rooms/${room.id}/invites/${invite.id}/decline`, { method: 'POST', headers: { 'Content-Type': 'application/json' } });
        if(res && res.ok){
          toast('Invitation declined.', 'success');
          // hide join-bar since user declined a private room invite (can't join otherwise)
          joinBarEl.innerHTML = '';
          const t2 = document.createElement('span'); t2.className = 'join-bar-text';
          t2.textContent = 'Invitation declined.';
          joinBarEl.appendChild(t2);
          loadPendingInvitations();
        } else {
          toast('Could not decline invite', 'error');
          declineBtn.disabled = false; declineBtn.textContent = 'Decline';
        }
      });
    }catch(e){ console.warn('refreshJoinBarForInvite error', e); }
  }

  // ── "My Invitations" sidebar section ──────────────────────────────────────

  async function loadPendingInvitations(){
    try{
      const section = document.getElementById('invitations-section');
      const list    = document.getElementById('invitations-list');
      if(!section || !list) return;

      const data = await api('/invitations/mine');
      const invites = (data && data.invites) || [];

      list.innerHTML = '';
      if(invites.length === 0){
        section.style.display = 'none';
        return;
      }

      section.style.display = '';
      invites.forEach(inv => {
        const li = document.createElement('li');
        li.className = 'invitation-item';
        li.dataset.inviteId = inv.id;
        li.dataset.roomId = inv.room_id;
        const roomName = escapeHtml(inv.room_name || ('Room ' + inv.room_id));
        li.innerHTML = `
          <span class="invitation-room-name">${roomName}</span>
          <div class="invitation-actions">
            <button type="button" class="btn-accept-invite btn-join" data-invite-id="${escapeHtml(String(inv.id))}" data-room-id="${escapeHtml(String(inv.room_id))}">Accept</button>
            <button type="button" class="btn-decline-invite" data-invite-id="${escapeHtml(String(inv.id))}" data-room-id="${escapeHtml(String(inv.room_id))}">Decline</button>
          </div>
        `;
        list.appendChild(li);
      });
    }catch(e){ console.warn('loadPendingInvitations error', e); }
  }

  // event delegation for accept/decline in the invitations sidebar list
  (function wireInvitationsList(){
    try{
      const section = document.getElementById('invitations-section');
      if(!section) return; // will retry via DOMContentLoaded
      attachInvitationsListeners(section);
    }catch(e){}
  })();

  function attachInvitationsListeners(section){
    try{
      section.addEventListener('click', async (e)=>{
        const btn = e.target;
        if(!btn || !btn.dataset || !btn.dataset.inviteId) return;
        const inviteId = btn.dataset.inviteId;
        const roomId   = btn.dataset.roomId;

        if(btn.classList.contains('btn-accept-invite')){
          btn.disabled = true; btn.textContent = 'Joining…';
          const res = await api(`/rooms/${roomId}/invites/${inviteId}/accept`, { method: 'POST', headers: { 'Content-Type': 'application/json' } });
          if(res && res.ok){
            toast('Joined room!', 'success');
            // remove invite item from list
            const li = btn.closest('.invitation-item');
            if(li) li.remove();
            checkInvitationsSectionEmpty();
            // add room to sidebar and load it
            try{
              const updated = await api(`/rooms/${encodeURIComponent(roomId)}`);
              if(updated && updated.room){
                window.rooms = window.rooms || [];
                if(!window.rooms.find(r => String(r.id) === String(roomId))) window.rooms.unshift(updated.room);
                try{ if(typeof window.renderRooms === 'function') window.renderRooms(); }catch(e){}
                try{ if(typeof window.selectRoom === 'function') window.selectRoom(updated.room); }catch(e){}
              }
            }catch(e){}
          } else {
            toast('Could not accept invite', 'error');
            btn.disabled = false; btn.textContent = 'Accept';
          }
        } else if(btn.classList.contains('btn-decline-invite')){
          btn.disabled = true; btn.textContent = 'Declining…';
          const res = await api(`/rooms/${roomId}/invites/${inviteId}/decline`, { method: 'POST', headers: { 'Content-Type': 'application/json' } });
          if(res && res.ok){
            toast('Invitation declined.', 'success');
            const li = btn.closest('.invitation-item');
            if(li) li.remove();
            checkInvitationsSectionEmpty();
          } else {
            toast('Could not decline invite', 'error');
            btn.disabled = false; btn.textContent = 'Decline';
          }
        }
      });
    }catch(e){}
  }

  function checkInvitationsSectionEmpty(){
    try{
      const section = document.getElementById('invitations-section');
      const list    = document.getElementById('invitations-list');
      if(section && list && list.children.length === 0) section.style.display = 'none';
    }catch(e){}
  }

  // ── hook into selectRoom ───────────────────────────────────────────────────

  // We wrap window.selectRoom after load to inject our invite-aware logic.
  function hookSelectRoom(){
    try{
      const orig = window.selectRoom;
      if(!orig || orig.__invitationsHooked) return;
      function hooked(roomOrId){
        const ret = orig(roomOrId);
        // run invite refresh after a short tick so selectRoom finishes first
        setTimeout(()=>{
          try{
            const room = window.currentRoom;
            if(!room) return;
            refreshInviteButton(room);
            // only refresh join-bar for non-members (joinBarEl visible)
            const joinBarEl = document.getElementById('join-bar');
            if(joinBarEl && joinBarEl.style.display !== 'none'){
              refreshJoinBarForInvite(room);
            }
          }catch(e){}
        }, 50);
        return ret;
      }
      hooked.__invitationsHooked = true;
      window.selectRoom = hooked;
      // also update roomsApi reference so modules using window.roomsApi.selectRoom get the hook
      try{ if(window.roomsApi) window.roomsApi.selectRoom = hooked; }catch(e){}
    }catch(e){}
  }

  // ── init ───────────────────────────────────────────────────────────────────

  function init(){
    // attach invitations list listeners
    try{
      const section = document.getElementById('invitations-section');
      if(section) attachInvitationsListeners(section);
    }catch(e){}

    // hook selectRoom once data/rooms.js has set it
    hookSelectRoom();

    // load pending invitations on startup
    loadPendingInvitations();

    // expose for external use
    try{
      window.invitationsApi = {
        refreshInviteButton,
        refreshJoinBarForInvite,
        loadPendingInvitations,
      };
    }catch(e){}
  }

  // run after DOM is ready
  if(document.readyState === 'loading'){
    document.addEventListener('DOMContentLoaded', init);
  } else {
    // defer slightly so data/rooms.js selectRoom is registered first
    setTimeout(init, 0);
  }

})();
