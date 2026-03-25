document.addEventListener('DOMContentLoaded', ()=>{
  // Ensure modal/toast root containers exist so pages without explicit markup still get modals/toasts
  try{
    if(!document.getElementById('modal-root')){
      const m = document.createElement('div'); m.id = 'modal-root'; document.body.appendChild(m);
    }
    if(!document.getElementById('toast-root')){
      const t = document.createElement('div'); t.id = 'toast-root'; document.body.appendChild(t);
    }
  }catch(e){}

  // minimal i18n (kept small and consistent with main.js)
  window._STRINGS = window._STRINGS || { en: { ok: 'OK', cancel: 'Cancel', ban: 'Ban', keep: 'Keep', revoke: 'Revoke' } };
  function t(key, lang='en'){ return (window._STRINGS[lang] && window._STRINGS[lang][key]) || window._STRINGS.en[key] || key; }
  const roomsList = document.getElementById('rooms-list');
  const contactsList = document.getElementById('contacts-list');
  const membersList = document.getElementById('members-list');
  const messagesEl = document.getElementById('messages');
  const roomTitle = document.getElementById('room-title');
  const composer = document.getElementById('composer');
  const input = document.getElementById('message-input');
  const roomsSection = document.getElementById('rooms-section');
  const roomsToggle = document.getElementById('rooms-toggle');
  const unreadTotalBtn = document.getElementById('unread-total');

  // runtime state
  let rooms = [];
  let contacts = [];
  let isDialog = false;
  // track last seen total so we can animate on increase
  let lastUnreadTotal = 0;
  // timestamp of the most recent local send action (ms since epoch)
  let lastLocalSendAt = 0;

  // Unread panel behavior is implemented in the shared module static/unread.js
  // Call the shared attachment helper if available so all pages use the same logic.
  try{ if(typeof attachUnreadHandlers === 'function') attachUnreadHandlers(); }catch(e){}

  // If the header is injected later, re-attach handlers via shared helper
  window.addEventListener('shared-header-loaded', ()=>{ try{ if(typeof attachUnreadHandlers === 'function') attachUnreadHandlers(); }catch(e){} try{ const adminBtn = document.getElementById('admin-open'); if(adminBtn){ adminBtn.addEventListener && adminBtn.addEventListener('click', async ()=>{ /* admin binding exists in main.js as well */ }); } }catch(e){} });


  // Admin UI: open admin panel when admin-open button clicked
  const adminOpenBtn = document.getElementById('admin-open');
  if(adminOpenBtn){
    adminOpenBtn.addEventListener('click', async ()=>{
      if(typeof window.openAdminPanel === 'function') return window.openAdminPanel();
      // fallback: simple list
      try{
        const panel = await fetchJSON('/admin/users'); const users = (panel && panel.users) || [];
        const root = document.getElementById('modal-root') || (function(){ const r=document.createElement('div'); r.id='modal-root'; document.body.appendChild(r); return r; })();
        root.innerHTML = '';
        const p = document.createElement('div'); p.className = 'admin-panel'; const ul = document.createElement('ul'); ul.style.listStyle='none'; ul.style.padding='0'; users.forEach(u=>{ const li = document.createElement('li'); li.textContent = `${u.id} - ${u.email}`; ul.appendChild(li); }); p.appendChild(ul); root.appendChild(p);
      }catch(e){ console.warn('fallback admin open failed', e); }
    });
  }

  function renderRooms(){
    roomsList.innerHTML = '';
    rooms.forEach(r=>{
      const li = document.createElement('li');
      const title = document.createElement('span');
      title.textContent = r.name;
      li.appendChild(title);
      const badge = document.createElement('span'); badge.className = 'unread-badge hidden'; badge.textContent = '0'; li.appendChild(badge);
      li.dataset.id = r.id;
      li.addEventListener('click', ()=>selectRoom(r));
      roomsList.appendChild(li);
    });
  }
  function renderMembers(list){
    membersList.innerHTML = '';
    list.forEach(m=>{
      const li = document.createElement('li');
      const dot = document.createElement('span');
      dot.className = 'online-dot ' + (m.online? 'online':'offline');
      li.appendChild(dot);
      const txt = document.createTextNode(m.name);
      li.appendChild(txt);
      membersList.appendChild(li);
    });
  }
  function renderContacts(){
    contactsList.innerHTML = '';
    contacts.forEach(c=>{
      const li = document.createElement('li');

        // after appending a message, refresh unread badges (keeps UI in sync when new messages arrive)
        try{ if(typeof loadUnreadSummary === 'function') loadUnreadSummary(); }catch(e){}
      const title = document.createElement('span'); title.textContent = c.name; li.appendChild(title);
      const badge = document.createElement('span'); badge.className='unread-badge hidden'; badge.textContent='0'; li.appendChild(badge);
      li.dataset.id = c.id;
      li.addEventListener('click', ()=>openDialog(c));
      contactsList.appendChild(li);
    });
  }

  // Load unread summary from server and update badges
  async function loadUnreadSummary(){
    const data = await fetchJSON('/notifications/unread-summary');
    if(!data) return;
    const roomMap = {};
    (data.rooms||[]).forEach(r=>{ roomMap[String(r.room_id)] = r.unread_count; });
    const dialogsMap = {};
    (data.dialogs||[]).forEach(d=>{ dialogsMap[String(d.other_id)] = d.unread_count; });
    // update room badges
    Array.from(roomsList.children).forEach(li=>{
      const id = li.dataset.id;
      const badge = li.querySelector('.unread-badge');
      const count = roomMap[String(id)] || 0;
      if(badge){ badge.textContent = String(count); badge.classList.toggle('hidden', count===0); }
    });
    // update contact/dialog badges
    Array.from(contactsList.children).forEach(li=>{
      const id = li.dataset.id;
      const badge = li.querySelector('.unread-badge');
      const count = dialogsMap[String(id)] || 0;
      if(badge){ badge.textContent = String(count); badge.classList.toggle('hidden', count===0); }
    });
    // update aggregated unread total in header if present
    try{
      const total = (data.rooms||[]).reduce((s,r)=>s + (r.unread_count||0), 0) + (data.dialogs||[]).reduce((s,d)=>s + (d.unread_count||0), 0);
      const btn = document.getElementById('unread-total');
      const live = document.getElementById('unread-live');
      if(btn){
        // Always display the unread total. When zero, apply a muted style instead of hiding.
        btn.classList.toggle('muted', total === 0);
        btn.removeAttribute('aria-hidden');
        btn.innerHTML = `<span class="unread-icon">📨</span><span class="unread-count">${total}</span>`;
        let inlineBadge = btn.parentNode.querySelector('.unread-badge-inline');
        if(!inlineBadge){ inlineBadge = document.createElement('span'); inlineBadge.className = 'unread-badge-inline'; btn.parentNode.appendChild(inlineBadge); }
        inlineBadge.textContent = total > 99 ? '99+' : String(total);
        inlineBadge.style.display = total > 0 ? 'inline-block' : 'none';
        if(live) live.textContent = `You have ${total} unread messages`;
      }
    }catch(e){ console.warn('loadUnreadSummary failed', e); }
  }

  // autoscroll logic: only auto-scroll when user is at or near bottom
  let autoscroll = true;
  function userIsAtBottom(){
    const threshold = 40; // px
    return messagesEl.scrollHeight - messagesEl.scrollTop - messagesEl.clientHeight < threshold;
  }
  messagesEl.addEventListener('scroll', ()=>{
    // if user scrolls up, disable autoscroll
    autoscroll = userIsAtBottom();
    // infinite scroll trigger: when near top, load older messages
    if(messagesEl.scrollTop < 50 && currentRoom){
      // load older messages
      if(isDialog){
        loadDialogMessages(currentRoom.id, {before: earliestTimestamp, prepend: true});
      } else {
        loadRoomMessages(currentRoom.id, {before: earliestTimestamp, prepend: true});
      }
    }
  });

  // track earliest message timestamp currently rendered for infinite scroll
  let earliestTimestamp = null;
  let latestTimestamp = null;

  composer.addEventListener('submit', (e)=>{
    e.preventDefault();
    try{ 
      lastLocalSendAt = Date.now(); 
      // subtle local pulse to acknowledge the user's send
      const btn = document.getElementById('unread-total');
      if(btn){ btn.classList.remove('pulse-local'); void btn.offsetWidth; btn.classList.add('pulse-local'); setTimeout(()=>btn.classList.remove('pulse-local'), 600); }
    }catch(e){}
    const text = input.value.trim();
    const composerEl = document.getElementById('composer');
    const replyTo = composerEl.dataset.replyTo || null;
    const fileEl = document.getElementById('file-input');
    const fileSelected = fileEl && fileEl.files && fileEl.files.length > 0;
    if(!text && !fileSelected) return;
  // create a pending placeholder instead of optimistic duplicate append
  const placeholder = document.createElement('div');
  placeholder.className = 'message pending me';
  const phMeta = document.createElement('div'); phMeta.className='meta'; phMeta.textContent = 'you';
  const phBody = document.createElement('div'); phBody.className='body'; phBody.textContent = text || '';
  placeholder.appendChild(phMeta);
  placeholder.appendChild(phBody);
  // controls for retry/cancel
  const controls = document.createElement('div'); controls.className='controls';
  const status = document.createElement('span'); status.className='status';
  controls.appendChild(status);
  const retryBtn = document.createElement('button'); retryBtn.type='button'; retryBtn.textContent='Retry';
  const cancelBtn = document.createElement('button'); cancelBtn.type='button'; cancelBtn.textContent='Cancel';
  controls.appendChild(retryBtn);
  controls.appendChild(cancelBtn);
  placeholder.appendChild(controls);
  messagesEl.appendChild(placeholder);
  if(autoscroll) messagesEl.scrollTop = messagesEl.scrollHeight;
    // prepare payload
    const payload = { text };
    if(replyTo) payload.reply_to = Number(replyTo);
    input.value = '';
    if(!currentRoom) return;
    // If a file is selected, perform atomic upload using messages_with_file endpoint with progress
    if(fileSelected){
      const file = fileEl.files[0];
      const fd = new FormData();
      fd.append('text', text);
      if(replyTo) fd.append('reply_to', replyTo);
      fd.append('file', file, file.name);
      // per-attachment progress element
      const progressWrap = document.createElement('div'); progressWrap.className='attachment-progress';
      progressWrap.textContent = `Uploading ${file.name}: `;
      const prog = document.createElement('progress'); prog.max = 100; prog.value = 0; progressWrap.appendChild(prog);
      messagesEl.appendChild(progressWrap);
      const url = isDialog ? `/dialogs/${currentRoom.id}/messages_with_file` : `/rooms/${currentRoom.id}/messages_with_file`;
      const xhr = new XMLHttpRequest();
      xhr.open('POST', url);
      xhr.onload = function(){
        try{
          const json = JSON.parse(xhr.responseText);
          if(json && json.message){
            // construct full message object including files
            const fullMsg = Object.assign({}, json.message);
            if(json.file) fullMsg.files = [json.file];
            const el2 = appendMessage(fullMsg);
            // replace placeholder with the real message element
            messagesEl.replaceChild(el2, placeholder);
            latestTimestamp = json.message.created_at || latestTimestamp;
          }
        }catch(e){ console.error('parse response', e); }
        progressWrap.remove();
      };
  xhr.onerror = function(){ showToast('Upload failed', 'error'); progressWrap.remove(); };
      // on network error: mark placeholder as failed and show retry/cancel
      xhr.addEventListener('error', ()=>{
        if(placeholder){
          placeholder.classList.add('failed');
          status.textContent = 'Failed';
          showToast('Upload failed', 'error');
        }
      });
      xhr.upload.onprogress = function(ev){ if(ev.lengthComputable){ const pct = Math.round((ev.loaded/ev.total)*100); prog.value = pct; } };
      xhr.send(fd);
      // wire retry / cancel handlers
      retryBtn.addEventListener('click', ()=>{
        // clear failed state and re-send
        if(placeholder) placeholder.classList.remove('failed');
        status.textContent = '';
        // re-send by triggering the same XHR logic again (simple approach: reload page to re-run flow)
        // better approach: encapsulate send logic in a function; for now, re-submit by programmatically clicking send
        composer.querySelector('button[type=submit]').click();
      });
      cancelBtn.addEventListener('click', ()=>{ if(placeholder && placeholder.parentNode) placeholder.parentNode.removeChild(placeholder); });
    } else {
      if(isDialog){
        fetch(`/dialogs/${currentRoom.id}/messages`, {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(payload)})
          .then(r=>r.json())
          .then(json=>{
            if(json && json.message){
              const fullMsg = Object.assign({}, json.message);
              const el2 = appendMessage(fullMsg);
              messagesEl.replaceChild(el2, placeholder);
              latestTimestamp = json.message.created_at || latestTimestamp;
              if(autoscroll) messagesEl.scrollTop = messagesEl.scrollHeight;
            }
          }).catch(err=>{ console.error('send dialog message failed', err); // remove placeholder on error
            if(placeholder && placeholder.parentNode) placeholder.parentNode.removeChild(placeholder);
          });
      } else {
        fetch(`/rooms/${currentRoom.id}/messages`, {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(payload)})
          .then(r=>r.json())
          .then(json=>{
            if(json && json.message){
              const fullMsg = Object.assign({}, json.message);
              const el2 = appendMessage(fullMsg);
              messagesEl.replaceChild(el2, placeholder);
              latestTimestamp = json.message.created_at || latestTimestamp;
              if(autoscroll) messagesEl.scrollTop = messagesEl.scrollHeight;
            }
          }).catch(err=>{ console.error('send room message failed', err); if(placeholder && placeholder.parentNode) placeholder.parentNode.removeChild(placeholder); });
      }
    }
    // clear reply state
    const replyPreviewEl = document.getElementById('reply-preview');
    if(replyPreviewEl) replyPreviewEl.style.display = 'none';
    delete composerEl.dataset.replyTo;
  });

  // handle Shift+Enter for newline in textarea
  input.addEventListener('keydown', (ev)=>{
    if(ev.key === 'Enter' && ev.shiftKey){
      const start = input.selectionStart;
      const end = input.selectionEnd;
      const val = input.value;
      input.value = val.substring(0, start) + '\n' + val.substring(end);
      input.selectionStart = input.selectionEnd = start + 1;
      ev.preventDefault();
    }
  });

  // inline emoji picker
  const emojiBtn = document.getElementById('emoji-btn');
  const emojiPicker = document.getElementById('emoji-picker');
  const emojis = ['😀','😁','😂','🤣','😊','😍','😎','😅','🙂','😉','🙃','😘','🤔','😴','😡','👍','👎','🙏','🎉','🔥','💯','🚀','🌟','🍕','☕️','📎','📷','🖼️','🎵','✅','❌','➕','➖'];
  function buildEmojiPicker(){
    if(!emojiPicker) return;
    emojiPicker.innerHTML = '';
    const grid = document.createElement('div'); grid.className='emoji-grid';
    emojis.forEach(e=>{
      const btn = document.createElement('button'); btn.type='button'; btn.textContent = e;
      btn.addEventListener('click', ()=>{
        const pos = input.selectionStart || input.value.length;
        input.value = input.value.slice(0,pos) + e + input.value.slice(pos);
        input.focus();
        emojiPicker.style.display = 'none';
      });
      grid.appendChild(btn);
    });
    emojiPicker.appendChild(grid);
  }
  buildEmojiPicker();
  if(emojiBtn){
    emojiBtn.addEventListener('click', (ev)=>{
      ev.stopPropagation();
      if(!emojiPicker) return;
      emojiPicker.style.display = emojiPicker.style.display === 'block' ? 'none' : 'block';
    });
  }
  // hide picker when clicking elsewhere
  document.addEventListener('click', (ev)=>{ if(emojiPicker) emojiPicker.style.display='none'; });

  // file attachment handling with upload guard and spinner
  const fileInput = document.getElementById('file-input');
  let uploading = false;
  const uploadingIndicator = document.getElementById('uploading-indicator');
  // file selection preview: do not auto-upload; user will send with composer submit which uses atomic endpoint
  if(fileInput){
    const selectedWrap = document.createElement('div'); selectedWrap.className='selected-file';
    fileInput.parentNode.insertBefore(selectedWrap, fileInput.nextSibling);
    fileInput.addEventListener('change', ()=>{
      selectedWrap.innerHTML = '';
      if(!fileInput.files || fileInput.files.length === 0) return;
      const file = fileInput.files[0];
      const info = document.createElement('div'); info.textContent = `Selected: ${file.name} `;
      const remove = document.createElement('button'); remove.type='button'; remove.textContent='Remove';
      remove.addEventListener('click', ()=>{ fileInput.value=''; selectedWrap.innerHTML=''; });
      info.appendChild(remove);
      selectedWrap.appendChild(info);
    });
  }

  // reply cancel
  const replyCancel = document.getElementById('reply-cancel');
  if(replyCancel){
    replyCancel.addEventListener('click', ()=>{
      const rp = document.getElementById('reply-preview'); if(rp) rp.style.display='none';
      const composerEl = document.getElementById('composer'); delete composerEl.dataset.replyTo;
    });
  }

  // helper: basic fetch wrapper
  async function fetchJSON(url, opts){
    try{
      // default to sending cookies for same-origin authenticated endpoints
      opts = opts || {};
      if(typeof opts.credentials === 'undefined') opts.credentials = 'include';
      // ensure headers object exists
      opts.headers = opts.headers || {};
      try{ // allow tests to inject a bearer token into window.__AUTH_TOKEN which will be used for Authorization
        if(typeof window !== 'undefined' && window.__AUTH_TOKEN && !opts.headers['Authorization']){
          opts.headers['Authorization'] = 'Bearer ' + window.__AUTH_TOKEN;
        }
      }catch(e){}
      const r = await fetch(url, opts);
      if(!r.ok){
        console.warn('fetch failed', url, r.status);
        return null;
      }
      // try to parse JSON, but return null on parse errors
      const json = await r.json().catch(()=>null);
      return json;
    }catch(e){ console.warn('fetchJSON failed', e); return null; }
  }

  async function loadRooms(){
    const data = await fetchJSON('/rooms');
    if(data && data.rooms){
      rooms = data.rooms;
      renderRooms();
      if(rooms.length) {
        // Tests may set window.__TEST_SKIP_AUTOSELECT to prevent automatic room open
        if(!(typeof window !== 'undefined' && window.__TEST_SKIP_AUTOSELECT)) selectRoom(rooms[0]);
      }
    }
  }

  async function loadContacts(){
    const data = await fetchJSON('/friends');
    if(data && data.friends){
      contacts = data.friends.map(f=>({id: f.id, name: f.username || f.email || ('user'+f.id)}));
      renderContacts();
    }
  }

  async function loadRoomMembers(roomId){
    const data = await fetchJSON(`/rooms/${roomId}`);
    if(!data || !data.room) return renderMembers([]);
    const memberIds = data.room.members || [];
    if(memberIds.length === 0) return renderMembers([]);
    // batch presence and user lookup
    const idsParam = memberIds.join(',');
    const [presResp, usersResp] = await Promise.all([
      fetchJSON(`/presence?ids=${encodeURIComponent(idsParam)}`),
      fetchJSON(`/users?ids=${encodeURIComponent(idsParam)}`)
    ]);
    const statuses = (presResp && presResp.statuses) || {};
    const users = (usersResp && usersResp.users) || [];
    const nameById = {};
    users.forEach(u => { nameById[String(u.id)] = u.username || u.email || ('user' + u.id); });
    const members = memberIds.map(id => ({ name: nameById[String(id)] || ('user ' + id), online: statuses[String(id)] === 'online' }));
    renderMembers(members);
  }

  async function loadRoomMessages(roomId, opts){
    opts = opts || {};
    const before = opts.before ? `?before=${encodeURIComponent(opts.before)}` : '';
    const data = await fetchJSON(`/rooms/${roomId}/messages${before}`);
    if(!data || !data.messages) return;
    // if prepend: preserve scroll position
    if(opts.prepend){
      const oldScrollHeight = messagesEl.scrollHeight;
      const frag = document.createDocumentFragment();
      data.messages.forEach(m=>{
        // pass the full message object so appendMessage can access id, reply, files, etc.
        const el = appendMessage(m);
        frag.insertBefore(el, frag.firstChild);
        earliestTimestamp = earliestTimestamp ? Math.min(earliestTimestamp, m.created_at) : m.created_at;
      });
      messagesEl.insertBefore(frag, messagesEl.firstChild);
      // restore scroll position to where the user was
      const newScrollHeight = messagesEl.scrollHeight;
      messagesEl.scrollTop = newScrollHeight - oldScrollHeight + messagesEl.scrollTop;
    } else {
      messagesEl.innerHTML = '';
      data.messages.forEach(m=>{
        const el = appendMessage(m);
        messagesEl.appendChild(el);
        earliestTimestamp = earliestTimestamp ? Math.min(earliestTimestamp, m.created_at) : m.created_at;
        latestTimestamp = m.created_at || latestTimestamp;
      });
      // initial load: scroll to bottom
      messagesEl.scrollTop = messagesEl.scrollHeight;
      autoscroll = true;
    }
  }

  async function loadDialogMessages(otherId, opts){
    opts = opts || {};
    const before = opts.before ? `?before=${encodeURIComponent(opts.before)}` : '';
    const data = await fetchJSON(`/dialogs/${otherId}/messages${before}`);
    if(!data || !data.messages) return;
    if(opts.prepend){
      const oldScrollHeight = messagesEl.scrollHeight;
      const frag = document.createDocumentFragment();
      data.messages.forEach(m=>{
        const el = appendMessage(m);
        frag.insertBefore(el, frag.firstChild);
        earliestTimestamp = earliestTimestamp ? Math.min(earliestTimestamp, m.created_at) : m.created_at;
      });
      messagesEl.insertBefore(frag, messagesEl.firstChild);
      const newScrollHeight = messagesEl.scrollHeight;
      messagesEl.scrollTop = newScrollHeight - oldScrollHeight + messagesEl.scrollTop;
    } else {
      messagesEl.innerHTML = '';
      data.messages.forEach(m=>{
        const el = appendMessage(m);
        messagesEl.appendChild(el);
        earliestTimestamp = earliestTimestamp ? Math.min(earliestTimestamp, m.created_at) : m.created_at;
        latestTimestamp = m.created_at || latestTimestamp;
      });
      messagesEl.scrollTop = messagesEl.scrollHeight;
      autoscroll = true;
    }
  }

  // bootstrap auth via /refresh; if unauthenticated redirect to login page
  async function bootstrap(){
    const r = await fetch('/refresh', {method: 'POST', credentials: 'include'}).catch(()=>null);
    if(!r || r.status === 401){
      // redirect to the hosted login page which will set cookie on success
      location.href = '/static/login.html';
      return;
    }
    // if logged in, the response contains token and user metadata
    try{
      const body = await r.json();
      const user = body.user;
      if(user){
        const ui = document.getElementById('user-info');
        if(ui){
          // render avatar initial, name and a dropdown trigger
          const display = escapeHtml(user.username || user.email || ('user'+user.id));
          ui.innerHTML = `
            <div class="user-dropdown">
              <div class="user-toggle" id="user-toggle" tabindex="0">
                <span class="avatar">${escapeHtml((user.username||user.email||'U').charAt(0).toUpperCase())}</span>
                <strong>${display}</strong>
                ${user.is_admin? '<span class="badge">admin</span>':''}
              </div>
              <div class="dropdown-panel" id="user-panel" style="display:none">
                <h4>Sessions</h4>
                <ul class="sessions-list" id="sessions-list"><li class="meta">Loading…</li></ul>
                <div style="margin-top:8px;display:flex;gap:8px;justify-content:space-between">
                  <button id="btn-logout-inline" type="button">Logout</button>
                  <button id="btn-refresh-sessions" type="button">Refresh</button>
                </div>
              </div>
            </div>
          `;
          // wire toggle and inline logout
          const toggle = document.getElementById('user-toggle');
          const panel = document.getElementById('user-panel');
          const sessionsList = document.getElementById('sessions-list');
          const refreshBtn = document.getElementById('btn-refresh-sessions');
          const inlineLogout = document.getElementById('btn-logout-inline');
          function closePanel(){ if(panel) panel.style.display='none'; }
          function openPanel(){ if(panel) panel.style.display='block'; loadSessions(); }
          toggle.addEventListener('click', ()=>{ if(panel.style.display==='block') closePanel(); else openPanel(); });
          refreshBtn.addEventListener('click', ()=> loadSessions());
          inlineLogout.addEventListener('click', async ()=>{ try{ await fetch('/logout', {method:'POST', credentials:'include'}); }catch(e){} location.href='/static/login.html'; });

          async function loadSessions(){
            sessionsList.innerHTML = '<li class="meta">Loading…</li>';
            try{
              const data = await fetchJSON('/sessions');
              if(!data || !data.sessions) return sessionsList.innerHTML = '<li class="meta">No sessions</li>';
              sessionsList.innerHTML = '';
              data.sessions.forEach(s => {
                const li = document.createElement('li');
                const meta = document.createElement('div'); meta.className='meta'; meta.textContent = `jti: ${s.jti} • last active: ${new Date((s.last_active||s.created_at||0)*1000).toLocaleString()}`;
                const btn = document.createElement('button'); btn.type='button'; btn.textContent='Revoke';
                btn.addEventListener('click', async ()=>{
                  // nicer modal confirmation instead of native confirm
                  const ok = await showModal({title:'Revoke session', body:'Revoke this session? This will immediately log out that session.', confirmText:'Revoke', cancelText:'Keep'});
                  if(!ok) return;
                  try{
                    btn.disabled = true;
                    const r = await fetch('/sessions/revoke', {method:'POST', credentials:'include', headers:{'Content-Type':'application/json'}, body: JSON.stringify({jti: s.jti})});
                    if(r && r.ok){
                      li.style.transition = 'opacity 220ms'; li.style.opacity = '0';
                      setTimeout(()=>{ li.remove(); showToast('Session revoked', 'success'); }, 260);
                    } else {
                      btn.disabled = false; showToast('Failed to revoke session', 'error');
                    }
                  }catch(e){ console.warn('revoke failed', e); btn.disabled = false; showToast('Failed to revoke session', 'error'); }
                });
                li.appendChild(meta); li.appendChild(btn); sessionsList.appendChild(li);
              });
            }catch(e){ sessionsList.innerHTML = '<li class="meta">Error loading sessions</li>'; }
          }
          // show admin button when user is admin
          try{ const adminBtn = document.getElementById('admin-open'); if(adminBtn) adminBtn.style.display = user.is_admin ? 'inline-flex' : 'none'; }catch(e){}
        }
      }
    }catch(e){ console.warn('refresh parse failed', e); }
    // ready: load data
    await loadRooms();
    await loadContacts();
    // update unread notification badges
    try{ await loadUnreadSummary(); }catch(e){}
  }

  // simple escape for username rendering
  function escapeHtml(str){
    return String(str).replace(/[&<>"']/g, (s)=>({ '&':'&amp;', '<':'&lt;', '>':'&gt;', '"':'&quot;', "'":"&#39;" }[s]));
  }

  // Modal utility: returns a Promise<boolean>
  function showModal(opts){
    // ensure modal root exists (should be created on DOMContentLoaded, but guard here)
    let root = document.getElementById('modal-root');
    if(!root){ try{ root = document.createElement('div'); root.id = 'modal-root'; document.body.appendChild(root); }catch(e){} }
    return new Promise((resolve)=>{
      root.innerHTML = '';
      const previouslyFocused = document.activeElement;
      const backdrop = document.createElement('div'); backdrop.className = 'modal-backdrop';
      const box = document.createElement('div'); box.className = 'modal-box';
      const title = document.createElement('h3');
      const titleId = 'modal-title-' + Math.random().toString(36).slice(2,9);
      title.id = titleId;
      title.textContent = opts.title || 'Confirm';
  const body = document.createElement('div'); body.className = 'modal-body'; body.innerHTML = `${escapeHtml(opts.body || '')}`;
  const actions = document.createElement('div'); actions.className = 'modal-actions';
  const cancel = document.createElement('button'); cancel.type='button'; cancel.textContent = opts.cancelText || t('cancel');
  const confirm = document.createElement('button'); confirm.type='button'; confirm.textContent = opts.confirmText || t('ok'); confirm.className='confirm';
      actions.appendChild(cancel); actions.appendChild(confirm);
      box.appendChild(title); box.appendChild(body); box.appendChild(actions);
      // accessibility
      box.setAttribute('role', 'dialog');
      box.setAttribute('aria-modal', 'true');
      box.setAttribute('aria-labelledby', titleId);
      backdrop.appendChild(box);
      root.appendChild(backdrop);

      // focus management / trap
      const focusable = [confirm, cancel];
      let focusIndex = 0;
      function focusFirst(){ focusIndex = 0; focusable[focusIndex].focus(); }
      function handleKey(e){
        if(e.key === 'Escape'){
          e.preventDefault(); cleanup(); resolve(false);
        } else if(e.key === 'Tab'){
          // simple two-element trap
          e.preventDefault();
          if(e.shiftKey) focusIndex = (focusIndex - 1 + focusable.length) % focusable.length;
          else focusIndex = (focusIndex + 1) % focusable.length;
          focusable[focusIndex].focus();
        }
      }

      function cleanup(){
        root.innerHTML = '';
        document.removeEventListener('keydown', handleKey);
        try{ if(previouslyFocused && previouslyFocused.focus) previouslyFocused.focus(); }catch(e){}
      }

      cancel.addEventListener('click', ()=>{ cleanup(); resolve(false); });
      backdrop.addEventListener('click', (e)=>{ if(e.target === backdrop){ cleanup(); resolve(false); } });
      confirm.addEventListener('click', ()=>{ cleanup(); resolve(true); });

      // wire key handler and initial focus
      document.addEventListener('keydown', handleKey);
      // wait a tick then focus the confirm button for quick confirmation via keyboard
      setTimeout(()=>{ try{ confirm.focus(); }catch(e){} }, 0);
    });
  }

  // Toast utility
  function showToast(msg, type='success', timeout=3000){
    let root = document.getElementById('toast-root');
    if(!root){
      try{
        root = document.createElement('div'); root.id = 'toast-root'; document.body.appendChild(root);
      }catch(e){ console.warn('toast fallback:', msg); return; }
    }
    if(!root.querySelector('.toast-container')){
      const cont = document.createElement('div'); cont.className='toast-container';
      // accessibility: polite live region for toasts
      cont.setAttribute('role', 'status');
      cont.setAttribute('aria-live', 'polite');
      cont.setAttribute('aria-atomic', 'false');
      root.appendChild(cont);
    }
    const cont = root.querySelector('.toast-container');
    const t = document.createElement('div'); t.className = 'toast ' + (type==='success'? 'success': (type==='error'? 'error':''));
    t.textContent = msg;
    // each toast should be perceived by assistive tech
    t.setAttribute('role', 'status');
    cont.appendChild(t);
    setTimeout(()=>{ t.style.opacity='0'; t.style.transform='translateY(8px)'; setTimeout(()=>t.remove(), 240); }, timeout);
  }

  // wire logout button
  const logoutBtn = document.getElementById('btn-logout');
  if(logoutBtn){
    logoutBtn.addEventListener('click', async ()=>{
      try{
        await fetch('/logout', {method:'POST', credentials:'include'});
      }catch(e){}
      // redirect to login page
      location.href = '/static/login.html';
    });
  }

  bootstrap();

  roomsToggle.addEventListener('click', ()=>{
    roomsSection.classList.toggle('compacted');
  });
});
