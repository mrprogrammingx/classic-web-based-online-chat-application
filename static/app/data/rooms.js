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

  /**
   * Scan all returned messages for edits and patch matching DOM nodes in-place.
   * Edited messages keep their original created_at so the incremental filter
   * (m.created_at > latestTimestamp) never picks them up — this function fills
   * that gap by comparing the edited_at stamp we track per message id.
   */
  function patchEditedMessages(messages){
    try{
      if(!messages || !messages.length) return;
      const container = (window.messagesEl) || document.getElementById('messages');
      if(!container) return;
      window.__editedAtCache = window.__editedAtCache || {};
      messages.forEach(m => {
        try{
          if(!m.id) return;
          const key = String(m.id);
          const cachedEditedAt = window.__editedAtCache[key];
          const currentEditedAt = m.edited_at || null;
          // If edited_at changed (or appeared for the first time) patch the node
          if(currentEditedAt && currentEditedAt !== cachedEditedAt){
            window.__editedAtCache[key] = currentEditedAt;
            const node = container.querySelector('[data-id="' + key + '"]');
            if(node && node.isConnected){
              const bodyEl = node.querySelector('.body');
              if(bodyEl && m.text != null) bodyEl.textContent = m.text;
              const metaEl = node.querySelector('.meta');
              if(metaEl){
                let ed = metaEl.querySelector('.edited');
                if(!ed){
                  ed = document.createElement('span');
                  ed.className = 'edited';
                  ed.textContent = ' (edited)';
                  metaEl.appendChild(ed);
                }
              }
            }
          } else if(!currentEditedAt) {
            // No edit yet — just prime the cache so a future change is detected
            window.__editedAtCache[key] = window.__editedAtCache[key] || null;
          }
        }catch(e){}
      });
    }catch(e){}
  }

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
          // try to select the requested room by id from the already-loaded list first
          const found = (window.rooms||[]).find(r => String(r.id) === String(requested));
          if(found){ selectRoom(found); return; }
          // not in the list (private room, or beyond the page limit) — fetch it directly
          try{
            const roomData = await window.fetchJSON(`/rooms/${encodeURIComponent(requested)}`);
            if(roomData && roomData.room){
              // inject into window.rooms so the sidebar renders it and the active highlight works
              window.rooms = window.rooms || [];
              if(!window.rooms.find(r => String(r.id) === String(roomData.room.id))){
                window.rooms.unshift(roomData.room);
              }
              try{ if(typeof window.renderRooms === 'function') window.renderRooms(); }catch(e){}
              selectRoom(roomData.room); return;
            }
          }catch(e){ console.warn('failed to fetch requested room directly', e); }
        }
        // otherwise, if nothing requested, do the previous auto-select behaviour
        if(window.rooms && window.rooms.length && !(window.__TEST_SKIP_AUTOSELECT) && !window.currentRoom){
          selectRoom(window.rooms[0]);
        }
      }catch(e){}
    }
  }

  async function loadMyRooms(){
    try{
      const data = await window.fetchJSON('/rooms/mine');
      if(data && data.rooms){
        window.myRooms = data.rooms;
        try{ if(typeof window.renderMyRooms === 'function') window.renderMyRooms(); }catch(e){}
      }
    }catch(e){}
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
    const members = memberIds.map(id => ({ name: nameById[String(id)] || ('user ' + id), online: statuses[String(id)] === 'online', status: statuses[String(id)] || 'offline' }));
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
    if(!data || !data.messages){
      // Handle access denied (ban / lost membership)
      try{
        if(data === null){
          const messagesElErr = (window && window.messagesEl) ? window.messagesEl : document.getElementById('messages');
          if(messagesElErr){
            messagesElErr.innerHTML = '<p style="padding:16px;color:#888;text-align:center">You no longer have access to this room\'s messages and files.</p>';
          }
          // hide composer
          const composerEl = document.getElementById('composer');
          if(composerEl) composerEl.style.display = 'none';
          const joinBarEl = document.getElementById('join-bar');
          if(joinBarEl) joinBarEl.style.display = 'none';
          // stop polling for this room
          stopMessagePoll();
        }
      }catch(e){}
      return;
    }
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
          // patch any messages that were edited since the last poll
          patchEditedMessages(data.messages);
        } else if(window.messagesEl){
          messagesEl.innerHTML = '';
          data.messages.forEach(m=>{ try{ let el = null; if(typeof window.appendMessage === 'function'){ el = window.appendMessage(m); } else { el = document.createElement('div'); el.className = 'message'; el.textContent = m.text || ''; } if(messagesEl) messagesEl.appendChild(el); window.earliestTimestamp = window.earliestTimestamp ? Math.min(window.earliestTimestamp, m.created_at) : m.created_at; window.latestTimestamp = m.created_at || window.latestTimestamp; }catch(e){} });
          if(messagesEl) { messagesEl.scrollTop = messagesEl.scrollHeight; window.autoscroll = true; }
          // mark that we've rendered the initial batch for this room
          try{ window._messagesRendered[String(roomId)] = true; }catch(e){}
          // seed the edited_at cache from the initial render
          patchEditedMessages(data.messages);
        }
      }catch(e){}
    }
  }

  // load unread summary used by tests to refresh badges
  let __unreadPollId = null;
  const UNREAD_POLL_INTERVAL = 5000; // 5 seconds

  async function loadUnreadSummary(){
    try{
      const data = await window.fetchJSON('/notifications/unread-summary');
      if(!data) return;
      let totalUnread = 0;

      // ── rooms badges ──────────────────────────────────────────────────
      try{
        const roomsListEl = document.getElementById('rooms-list');
        // build a set of room ids with unread counts for quick lookup
        const unreadRooms = {};
        if(data.rooms){
          data.rooms.forEach(rm => { unreadRooms[String(rm.room_id)] = Number(rm.unread_count) || 0; });
        }
        if(roomsListEl){
          Array.from(roomsListEl.querySelectorAll('li')).forEach(li => {
            try{
              const rid = li.dataset && li.dataset.id;
              if(!rid) return;
              const count = unreadRooms[String(rid)] || 0;
              // skip the currently open room — it's already been read
              const isActive = window.currentRoom && !window.isDialog && String(window.currentRoom.id) === String(rid);
              let badge = li.querySelector('.unread-badge');
              if(!badge){ badge = document.createElement('span'); badge.className = 'unread-badge'; li.appendChild(badge); }
              if(count > 0 && !isActive){
                badge.textContent = String(count);
                badge.classList.remove('hidden');
                totalUnread += count;
              } else {
                badge.classList.add('hidden');
              }
            }catch(e){}
          });
        }
      }catch(e){}

      // ── contacts / dialogs badges ─────────────────────────────────────
      try{
        const contactsListEl = document.getElementById('contacts-list');
        const unreadDialogs = {};
        if(data.dialogs){
          data.dialogs.forEach(d => { unreadDialogs[String(d.other_id)] = Number(d.unread_count) || 0; });
        }
        if(contactsListEl){
          Array.from(contactsListEl.querySelectorAll('li')).forEach(li => {
            try{
              const cid = li.dataset && li.dataset.id;
              if(!cid) return;
              const count = unreadDialogs[String(cid)] || 0;
              const isActive = window.currentRoom && window.isDialog && String(window.currentRoom.id) === String(cid);
              let badge = li.querySelector('.unread-badge');
              if(!badge){ badge = document.createElement('span'); badge.className = 'unread-badge'; li.appendChild(badge); }
              if(count > 0 && !isActive){
                badge.textContent = String(count);
                badge.classList.remove('hidden');
                totalUnread += count;
              } else {
                badge.classList.add('hidden');
              }
            }catch(e){}
          });
        }
        // also count dialog unreads from senders who aren't in the contacts list
        if(data.dialogs){
          data.dialogs.forEach(d => {
            const cid = String(d.other_id);
            const isActive = window.currentRoom && window.isDialog && String(window.currentRoom.id) === cid;
            if(!isActive){
              // only add to totalUnread if not already counted via the contacts DOM loop
              const contactsListEl2 = document.getElementById('contacts-list');
              const liInList = contactsListEl2 && contactsListEl2.querySelector('li[data-id="' + cid + '"]');
              if(!liInList){
                totalUnread += (Number(d.unread_count) || 0);
              }
            }
          });
        }
      }catch(e){}

      // ── header unread total button ────────────────────────────────────
      try{
        const countEl = document.querySelector('#unread-total .unread-count');
        if(countEl){
          countEl.textContent = String(totalUnread);
        }
        const btn = document.getElementById('unread-total');
        if(btn){
          if(totalUnread > 0){
            btn.classList.add('has-unread');
            btn.title = totalUnread + ' unread message' + (totalUnread !== 1 ? 's' : '');
          } else {
            btn.classList.remove('has-unread');
            btn.title = 'No unread messages';
          }
        }
        // update aria live region for screen readers
        const liveEl = document.getElementById('unread-live');
        if(liveEl && totalUnread > 0){
          liveEl.textContent = totalUnread + ' unread notification' + (totalUnread !== 1 ? 's' : '');
        }
      }catch(e){}

      // store for external use
      window.__lastUnreadData = data;
      window.__lastUnreadTotal = totalUnread;
    }catch(e){}
  }

  function startUnreadPoll(){
    try{
      stopUnreadPoll();
      // immediate fetch
      loadUnreadSummary();
      __unreadPollId = setInterval(loadUnreadSummary, UNREAD_POLL_INTERVAL);
    }catch(e){}
  }

  function stopUnreadPoll(){
    try{ if(__unreadPollId){ clearInterval(__unreadPollId); __unreadPollId = null; } }catch(e){}
  }

  async function loadDialogMessages(otherId, opts){
    opts = opts || {};
    const before = opts.before ? `?before=${encodeURIComponent(opts.before)}` : '';
    const data = await window.fetchJSON(`/dialogs/${otherId}/messages${before}`);
    if(!data || !data.messages) return;
    // Handle read_only flag (user-to-user ban): freeze the composer
    try{
      const composerEl = document.getElementById('composer');
      const joinBarEl  = document.getElementById('join-bar');
      const frozenBar  = document.getElementById('frozen-bar');
      if(data.read_only){
        // hide composer and join-bar, show frozen banner
        if(composerEl) composerEl.style.display = 'none';
        if(joinBarEl) joinBarEl.style.display = 'none';
        if(frozenBar){
          frozenBar.style.display = '';
        } else {
          // create the frozen bar dynamically
          const bar = document.createElement('div');
          bar.id = 'frozen-bar';
          bar.className = 'frozen-bar';
          bar.textContent = 'This conversation is frozen due to a ban. Messages are read-only.';
          // insert after messages area
          const parent = composerEl ? composerEl.parentNode : (window.messagesEl && window.messagesEl.parentNode);
          if(parent && composerEl) parent.insertBefore(bar, composerEl.nextSibling);
          else if(parent) parent.appendChild(bar);
        }
      } else {
        // ensure frozen bar is hidden when not read_only
        if(frozenBar) frozenBar.style.display = 'none';
        // restore composer for dialogs (join-bar stays hidden for dialogs)
        if(composerEl) composerEl.style.display = '';
        if(joinBarEl) joinBarEl.style.display = 'none';
      }
    }catch(e){}
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
          // patch any messages that were edited since the last poll
          patchEditedMessages(data.messages);
        } else if(window.messagesEl){
          window.messagesEl.innerHTML = '';
          data.messages.forEach(m=>{ const el = window.appendMessage(m); if(window.messagesEl) window.messagesEl.appendChild(el); window.earliestTimestamp = window.earliestTimestamp ? Math.min(window.earliestTimestamp, m.created_at) : m.created_at; window.latestTimestamp = m.created_at || window.latestTimestamp; });
          if(window.messagesEl) { window.messagesEl.scrollTop = window.messagesEl.scrollHeight; window.autoscroll = true; }
          try{ window._messagesRendered[String(otherId)] = true; }catch(e){}
          // seed the edited_at cache from the initial render
          patchEditedMessages(data.messages);
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
      // add clear messages button for owners/admins
      try{
        const header = document.querySelector('.messages-header');
        if(header){
          // remove existing button if present
          const existing = header.querySelector('.btn-clear-messages'); if(existing) existing.remove();
          const canClear = room && (String(room.owner) === String(window.__ME_ID) || (room.admins && Array.isArray(room.admins) && room.admins.indexOf(window.__ME_ID) !== -1));
          if(canClear){
            const btn = document.createElement('button'); btn.className = 'btn btn-danger btn-clear-messages'; btn.textContent = 'Clear messages';
            btn.style.marginLeft = '12px';
            btn.addEventListener('click', async ()=>{
              try{
                // ensure UI modal available
                let ok = true;
                try{ ok = await (window.showModal ? window.showModal({ title: 'Clear all messages', body: 'Remove all messages from this room? This cannot be undone.', confirmText: 'Clear', cancelText: 'Cancel' }) : Promise.resolve(window.confirm('Remove all messages from this room?'))); }catch(e){ ok = true; }
                if(!ok) return;
                const res = await window.fetchJSON(`/rooms/${room.id}/messages/clear`, { method: 'POST', headers: { 'Content-Type': 'application/json' } });
                if(res && res.ok){
                  try{ if(window.messagesEl) window.messagesEl.innerHTML = ''; }catch(e){}
                  window.showToast && window.showToast('Messages cleared','success');
                } else {
                  window.showToast && window.showToast('Failed to clear messages','error');
                }
              }catch(e){ console.warn('clear messages failed', e); window.showToast && window.showToast('Clear failed','error'); }
            });
            if(roomTitleEl) roomTitleEl.parentElement && roomTitleEl.parentElement.appendChild(btn);
            else header.appendChild(btn);
          }
        }
      }catch(e){}
      // clear messages and load
      try{ if(window.messagesEl) window.messagesEl.innerHTML = ''; }catch(e){}
        try{ window._messagesRendered = window._messagesRendered || {}; delete window._messagesRendered[String(room.id)]; }catch(e){}
      try{
        if(window.isDialog) loadDialogMessages(room.id);
        else loadRoomMessages(room.id);
      }catch(e){}
      // start polling for new messages for this room
      try{ startMessagePoll(room.id); }catch(e){}
      // load and display room members
      try{ if(!window.isDialog) loadRoomMembers(room.id); else { try{ if(typeof window.renderMembers === 'function') window.renderMembers([]); }catch(e){} } }catch(e){}
      // ── composer vs join-bar ─────────────────────────────────────────────
      // For public rooms the user hasn't joined, hide the message composer and
      // show a "Join Room" button instead. Dialogs are always composable.
      try{
        const composerEl = document.getElementById('composer');
        const joinBarEl  = document.getElementById('join-bar');
        const joinBarBtn = document.getElementById('join-bar-btn');
        if(composerEl && joinBarEl){
          // dialogs have no membership concept — always show composer
          const isMember = window.isDialog || room.is_dialog
            || room.is_member === true
            || room.is_owner  === true
            || room.is_admin  === true
            // owner_id match as a fallback when flags are absent
            || (room.owner_id && String(room.owner_id) === String(window.__ME_ID))
            // if members list present, check inclusion
            || (Array.isArray(room.members) && room.members.map(String).indexOf(String(window.__ME_ID)) !== -1);
          if(isMember){
            composerEl.style.display = '';
            joinBarEl.style.display  = 'none';
          } else {
            composerEl.style.display = 'none';
            joinBarEl.style.display  = '';
            // wire up join button (remove old listener first by cloning)
            if(joinBarBtn){
              const freshBtn = joinBarBtn.cloneNode(true);
              joinBarBtn.parentNode.replaceChild(freshBtn, joinBarBtn);
              freshBtn.addEventListener('click', async () => {
                try{
                  freshBtn.disabled = true;
                  freshBtn.textContent = 'Joining…';
                  const res = await window.fetchJSON(`/rooms/${room.id}/join`, { method: 'POST', headers: { 'Content-Type': 'application/json' } });
                  if(res !== null){
                    window.showToast && window.showToast('Joined room!', 'success');
                    // refresh room data so is_member is now true
                    const updated = await window.fetchJSON(`/rooms/${encodeURIComponent(room.id)}`);
                    const freshRoom = (updated && updated.room) ? updated.room : Object.assign({}, room, { is_member: true });
                    // update window.rooms entry
                    if(window.rooms){
                      const idx = window.rooms.findIndex(r => String(r.id) === String(room.id));
                      if(idx !== -1) window.rooms[idx] = freshRoom; else window.rooms.unshift(freshRoom);
                    }
                    // refresh My Rooms from backend
                    try{ if(typeof loadMyRooms === 'function') loadMyRooms(); }catch(e){}
                    selectRoom(freshRoom);
                  } else {
                    window.showToast && window.showToast('Could not join room', 'error');
                    freshBtn.disabled = false;
                    freshBtn.textContent = 'Join Room';
                  }
                }catch(e){ console.warn('join failed', e); freshBtn.disabled = false; freshBtn.textContent = 'Join Room'; }
              });
            }
          }
        }
      }catch(e){}
      // ────────────────────────────────────────────────────────────────────
      // mark active room/contact item and clear unread badge
      try{
        const roomsListEl = document.getElementById('rooms-list');
        if(roomsListEl){ Array.from(roomsListEl.querySelectorAll('li')).forEach(li=>{ li.classList.toggle('active', li.dataset && String(li.dataset.id) === String(room.id)); }); }
        // when room is selected, clear its unread badge
        try{ const li = document.querySelector(`#rooms-list li[data-id="${room.id}"]`); if(li){ const b = li.querySelector('.unread-badge'); if(b) b.classList.add('hidden'); } }catch(e){}
        // also highlight matching item in My Rooms list
        const myRoomsListEl = document.getElementById('my-rooms-list');
        if(myRoomsListEl){ Array.from(myRoomsListEl.querySelectorAll('li')).forEach(li=>{ li.classList.toggle('active', li.dataset && String(li.dataset.id) === String(room.id)); }); }
      }catch(e){}
      // for dialogs, also clear the contacts-list badge and highlight
      try{
        const contactsListEl = document.getElementById('contacts-list');
        if(contactsListEl){
          Array.from(contactsListEl.querySelectorAll('li')).forEach(li=>{
            const isActive = window.isDialog && li.dataset && String(li.dataset.id) === String(room.id);
            li.classList.toggle('active', isActive);
            if(isActive){
              const b = li.querySelector('.unread-badge');
              if(b) b.classList.add('hidden');
            }
          });
        }
      }catch(e){}
      // refresh unread badges shortly after (the messages GET will mark-as-read server-side)
      try{ setTimeout(function(){ loadUnreadSummary(); }, 1500); }catch(e){}
    }catch(e){}
  }

  try{ window.loadRooms = loadRooms; window.loadMyRooms = loadMyRooms; window.loadContacts = loadContacts; window.loadRoomMembers = loadRoomMembers; window.loadRoomMessages = loadRoomMessages; window.loadDialogMessages = loadDialogMessages; window.loadUnreadSummary = loadUnreadSummary; window.startUnreadPoll = startUnreadPoll; window.stopUnreadPoll = stopUnreadPoll; window.selectRoom = selectRoom; window.roomsApi = { loadRooms, loadMyRooms, loadContacts, loadRoomMembers, loadRoomMessages, loadDialogMessages, loadUnreadSummary, startUnreadPoll, stopUnreadPoll, selectRoom }; }catch(e){}

})();
