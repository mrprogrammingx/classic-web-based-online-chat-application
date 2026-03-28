// Rooms and messages loaders (extracted)
(function(){
  // poller id for message refresh
  let __messagePollId = null;
  let __messagePollInFlight = false;
  const MESSAGE_POLL_INTERVAL = 1000; // 1 second for quick delivery

  function startMessagePoll(roomId){
    try{
      stopMessagePoll();
      if(!roomId) return;
      // trigger immediate fetch once
      try{ if(window.currentRoom && String(window.currentRoom.id) === String(roomId)) { __messagePollInFlight = true; Promise.resolve().then(()=>loadRoomMessages(roomId)).finally(()=>{ __messagePollInFlight = false; }); } }catch(e){}
      __messagePollId = setInterval(async ()=>{
        try{
          if(__messagePollInFlight) return; // skip if previous fetch still running
          if(window.currentRoom && String(window.currentRoom.id) === String(roomId)){
            __messagePollInFlight = true;
            try{ await loadRoomMessages(roomId); }catch(e){}
            __messagePollInFlight = false;
          }
        }catch(e){ __messagePollInFlight = false; }
      }, MESSAGE_POLL_INTERVAL);
    }catch(e){}
  }

  function stopMessagePoll(){ try{ if(__messagePollId) { clearInterval(__messagePollId); __messagePollId = null; __messagePollInFlight = false; } }catch(e){} }

  async function loadRooms(){
    const data = await window.fetchJSON('/rooms');
    if(data && data.rooms){
      window.rooms = data.rooms;
      try{ if(typeof window.renderRooms === 'function') window.renderRooms(); }catch(e){}
      try{
        // prefer an explicitly requested room via bootstrap (from ?room=) if present
        // If a dialog was requested (e.g. ?dialog=<user_id>), open a dialog with that user
        // Prioritize dialog requests so ?dialog opens a personal chat even if a room
        // exists with the same id (avoid room/dialog id collisions).
        const requestedDialog = (typeof window.__REQUESTED_DIALOG !== 'undefined') ? window.__REQUESTED_DIALOG : null;
        if(requestedDialog){
          try{ selectRoom({ id: requestedDialog, other_id: requestedDialog, is_dialog: true, name: null }); return; }catch(e){}
        }
        const requested = (typeof window.__REQUESTED_ROOM !== 'undefined') ? window.__REQUESTED_ROOM : null;
        if(requested){
          // try to select the requested room by id; fall back to first room only if not found
          const found = (window.rooms||[]).find(r => String(r.id) === String(requested));
          if(found){ selectRoom(found); return; }
        }
        // otherwise, if nothing requested, do the previous auto-select behaviour
        if(window.rooms && window.rooms.length && !(window.__TEST_SKIP_AUTOSELECT) && !window.currentRoom){
          selectRoom(window.rooms[0]);
        }
      }catch(e){}
    }
  }

  async function loadContacts(){
    const data = await window.fetchJSON('/friends');
    if(data && data.friends){ window.contacts = data.friends.map(f=>({id: f.id, name: f.username || f.email || ('user'+f.id)})); try{ if(typeof window.renderContacts === 'function') window.renderContacts(); }catch(e){} }
  }

  async function loadRoomMembers(roomId){
    const data = await window.fetchJSON(`/rooms/${roomId}`);
    if(!data || !data.room) return window.renderMembers && window.renderMembers([]);
    const memberIds = data.room.members || [];
    if(memberIds.length === 0) return window.renderMembers && window.renderMembers([]);
    const idsParam = memberIds.join(',');
    const [presResp, usersResp] = await Promise.all([
      window.fetchJSON(`/presence?ids=${encodeURIComponent(idsParam)}`),
      window.fetchJSON(`/users?ids=${encodeURIComponent(idsParam)}`)
    ]);
    const statuses = (presResp && presResp.statuses) || {};
    const users = (usersResp && usersResp.users) || [];
    const nameById = {};
    users.forEach(u => { nameById[String(u.id)] = u.username || u.email || ('user' + u.id); });
    const members = memberIds.map(id => ({ name: nameById[String(id)] || ('user ' + id), online: statuses[String(id)] === 'online' }));
    try{ if(typeof window.renderMembers === 'function') window.renderMembers(members); }catch(e){}
  }

  async function loadRoomMessages(roomId, opts){
    opts = opts || {};
    const messagesEl = (window && window.messagesEl) ? window.messagesEl : document.getElementById('messages');
    // If the message renderer helper isn't available yet (race during boot),
    // retry a few times before giving up. This avoids silent failures where
    // loadRoomMessages runs before static/app/data/messages.js defines
    // window.appendMessage.
    try{
      if(typeof window.appendMessage !== 'function'){
        window.__loadRoomMessagesRetries = window.__loadRoomMessagesRetries || {};
        const key = String(roomId);
        window.__loadRoomMessagesRetries[key] = (window.__loadRoomMessagesRetries[key] || 0) + 1;
        if(window.__loadRoomMessagesRetries[key] <= 10){
          setTimeout(()=>{ try{ loadRoomMessages(roomId, opts); }catch(e){} }, 100);
          return;
        }
        // fall through and attempt to render once more; if appendMessage is still
        // missing the try/catch below will prevent a crash but messages won't render.
      }
    }catch(e){}
    const before = opts.before ? `?before=${encodeURIComponent(opts.before)}` : '';
  const data = await window.fetchJSON(`/rooms/${roomId}/messages${before}`);
  try{ console.debug && console.debug('loadRoomMessages fetched', roomId, (data && data.messages && data.messages.length) || 0, (data && data.messages && data.messages.map(m=>m.id)) ); }catch(e){}
    if(!data || !data.messages) return;
    if(opts.prepend){
      const oldScrollHeight = window.messagesEl && window.messagesEl.scrollHeight || 0;
      const frag = document.createDocumentFragment();
      data.messages.forEach(m=>{ const el = window.appendMessage(m); frag.insertBefore(el, frag.firstChild); window.earliestTimestamp = window.earliestTimestamp ? Math.min(window.earliestTimestamp, m.created_at) : m.created_at; });
      if(window.messagesEl) window.messagesEl.insertBefore(frag, window.messagesEl.firstChild);
      const newScrollHeight = window.messagesEl && window.messagesEl.scrollHeight || 0;
      if(window.messagesEl) window.messagesEl.scrollTop = newScrollHeight - oldScrollHeight + (window.messagesEl.scrollTop||0);
    } else {
      // append-only refresh: if we already have a latestTimestamp, append only newer messages
      try{
        // use an explicit rendered flag to detect whether we've done the initial full render
        window._messagesRendered = window._messagesRendered || {};
        const renderedForRoom = window._messagesRendered[String(roomId)];
        if(messagesEl && renderedForRoom){
          const wasDist = messagesEl.scrollHeight - messagesEl.scrollTop - messagesEl.clientHeight;
          const wasNearBottom = wasDist < 50;
          const newMsgs = data.messages.filter(m => (window.latestTimestamp == null) || (m.created_at > window.latestTimestamp));
          newMsgs.forEach(m=>{
            try{
              let el = null;
              if(typeof window.appendMessage === 'function'){
                el = window.appendMessage(m);
              } else {
                // minimal fallback element so tests can observe messages
                el = document.createElement('div'); el.className = 'message'; el.textContent = m.text || '';
              }
              try{ messagesEl.appendChild(el); }catch(e){}
              window.earliestTimestamp = window.earliestTimestamp ? Math.min(window.earliestTimestamp, m.created_at) : m.created_at;
              window.latestTimestamp = m.created_at || window.latestTimestamp;
            }catch(e){}
          });
          if((wasNearBottom || window.autoscroll) && newMsgs.length > 0){ try{ messagesEl.scrollTop = messagesEl.scrollHeight; }catch(e){} window.autoscroll = true; }
        } else if(window.messagesEl){
          messagesEl.innerHTML = '';
          data.messages.forEach(m=>{ try{ let el = null; if(typeof window.appendMessage === 'function'){ el = window.appendMessage(m); } else { el = document.createElement('div'); el.className = 'message'; el.textContent = m.text || ''; } if(messagesEl) messagesEl.appendChild(el); window.earliestTimestamp = window.earliestTimestamp ? Math.min(window.earliestTimestamp, m.created_at) : m.created_at; window.latestTimestamp = m.created_at || window.latestTimestamp; }catch(e){} });
          if(messagesEl) { messagesEl.scrollTop = messagesEl.scrollHeight; window.autoscroll = true; }
          // mark that we've rendered the initial batch for this room
          try{ window._messagesRendered[String(roomId)] = true; }catch(e){}
        }
      }catch(e){}
    }
  }

  // load unread summary used by tests to refresh badges
  async function loadUnreadSummary(){
    try{
      const data = await window.fetchJSON('/notifications/unread-summary');
      if(!data) return;
      // apply counts to DOM rooms list
      try{
        const roomsListEl = document.getElementById('rooms-list');
        if(roomsListEl && data.rooms){
          data.rooms.forEach(rm => {
            try{
              const li = Array.from(roomsListEl.querySelectorAll('li')).find(l => String(l.dataset.id) === String(rm.room_id));
              if(li){
                let badge = li.querySelector('.unread-badge');
                if(!badge){ badge = document.createElement('span'); badge.className = 'unread-badge'; li.appendChild(badge); }
                if(Number(rm.unread_count) > 0){ badge.textContent = String(Number(rm.unread_count)); badge.classList.remove('hidden'); } else { badge.classList.add('hidden'); }
              }
            }catch(e){}
          });
        }
      }catch(e){}
    }catch(e){}
  }

  async function loadDialogMessages(otherId, opts){
    opts = opts || {};
    const before = opts.before ? `?before=${encodeURIComponent(opts.before)}` : '';
    const data = await window.fetchJSON(`/dialogs/${otherId}/messages${before}`);
    if(!data || !data.messages) return;
    if(opts.prepend){
      const oldScrollHeight = window.messagesEl && window.messagesEl.scrollHeight || 0;
      const frag = document.createDocumentFragment();
      data.messages.forEach(m=>{ const el = window.appendMessage(m); frag.insertBefore(el, frag.firstChild); window.earliestTimestamp = window.earliestTimestamp ? Math.min(window.earliestTimestamp, m.created_at) : m.created_at; });
      if(window.messagesEl) window.messagesEl.insertBefore(frag, window.messagesEl.firstChild);
      const newScrollHeight = window.messagesEl && window.messagesEl.scrollHeight || 0;
      if(window.messagesEl) window.messagesEl.scrollTop = newScrollHeight - oldScrollHeight + (window.messagesEl.scrollTop||0);
    } else {
      // append-only refresh for dialogs as well
      try{
        window._messagesRendered = window._messagesRendered || {};
        const renderedForDialog = window._messagesRendered[String(otherId)];
        if(window.messagesEl && renderedForDialog){
          const wasDist = window.messagesEl.scrollHeight - window.messagesEl.scrollTop - window.messagesEl.clientHeight;
          const wasNearBottom = wasDist < 50;
          const newMsgs = data.messages.filter(m => (window.latestTimestamp == null) || (m.created_at > window.latestTimestamp));
          newMsgs.forEach(m=>{ const el = window.appendMessage(m); try{ window.messagesEl.appendChild(el); }catch(e){} window.earliestTimestamp = window.earliestTimestamp ? Math.min(window.earliestTimestamp, m.created_at) : m.created_at; window.latestTimestamp = m.created_at || window.latestTimestamp; });
          if((wasNearBottom || window.autoscroll) && newMsgs.length > 0){ try{ window.messagesEl.scrollTop = window.messagesEl.scrollHeight; }catch(e){} window.autoscroll = true; }
        } else if(window.messagesEl){
          window.messagesEl.innerHTML = '';
          data.messages.forEach(m=>{ const el = window.appendMessage(m); if(window.messagesEl) window.messagesEl.appendChild(el); window.earliestTimestamp = window.earliestTimestamp ? Math.min(window.earliestTimestamp, m.created_at) : m.created_at; window.latestTimestamp = m.created_at || window.latestTimestamp; });
          if(window.messagesEl) { window.messagesEl.scrollTop = window.messagesEl.scrollHeight; window.autoscroll = true; }
          try{ window._messagesRendered[String(otherId)] = true; }catch(e){}
        }
      }catch(e){}
    }
  }

  // canonical selectRoom lives here so room-related loading and DOM updates are colocated
  function selectRoom(roomOrId){
    try{
      let room = roomOrId;
      if(!room) return;
      if(typeof roomOrId === 'number' || typeof roomOrId === 'string'){
        room = (window.rooms||[]).find(r => String(r.id) === String(roomOrId)) || { id: roomOrId };
      }
      window.currentRoom = room;
      window.isDialog = !!room.is_dialog || false;
      // update title if present in DOM
      try{ const roomTitleEl = document.getElementById('room-title'); if(roomTitleEl) roomTitleEl.textContent = room.name || room.other_name || (window.isDialog ? 'Dialog' : 'Room'); }catch(e){}
      // clear messages and load
      try{ if(window.messagesEl) window.messagesEl.innerHTML = ''; }catch(e){}
        try{ window._messagesRendered = window._messagesRendered || {}; delete window._messagesRendered[String(room.id)]; }catch(e){}
      try{
        if(window.isDialog) loadDialogMessages(room.id);
        else loadRoomMessages(room.id);
      }catch(e){}
      // start polling for new messages for this room
      try{ startMessagePoll(room.id); }catch(e){}
      // mark active room item
      try{
        const roomsListEl = document.getElementById('rooms-list');
        if(roomsListEl){ Array.from(roomsListEl.querySelectorAll('li')).forEach(li=>{ li.classList.toggle('active', li.dataset && String(li.dataset.id) === String(room.id)); }); }
        // when room is selected, clear its unread badge
        try{ const li = document.querySelector(`#rooms-list li[data-id="${room.id}"]`); if(li){ const b = li.querySelector('.unread-badge'); if(b) b.classList.add('hidden'); } }catch(e){}
      }catch(e){}
    }catch(e){}
  }

  try{ window.loadRooms = loadRooms; window.loadContacts = loadContacts; window.loadRoomMembers = loadRoomMembers; window.loadRoomMessages = loadRoomMessages; window.loadDialogMessages = loadDialogMessages; window.loadUnreadSummary = loadUnreadSummary; window.selectRoom = selectRoom; window.roomsApi = { loadRooms, loadContacts, loadRoomMembers, loadRoomMessages, loadDialogMessages, loadUnreadSummary, selectRoom }; }catch(e){}

})();
