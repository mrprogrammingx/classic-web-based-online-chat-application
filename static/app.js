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
  // expose to extracted modules which use window.messagesEl
  try{ window.messagesEl = messagesEl; }catch(e){}
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

  // initialize messages UI (autoscroll + infinite-scroll) - implemented in static/app/messages-ui.js
  try{ if(window && typeof window.initMessagesUi === 'function') window.initMessagesUi(); }catch(e){}

  // track earliest message timestamp currently rendered for infinite scroll
  // expose timestamps to extracted rooms module
  try{ window.earliestTimestamp = null; window.latestTimestamp = null; }catch(e){}

  composer.addEventListener('submit', (e)=>{
    try{ if(window && typeof window.handleComposerSubmit === 'function') return window.handleComposerSubmit(e); }catch(err){ try{ e.preventDefault(); }catch(e){} }
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

  // initialize emoji picker (extracted to static/app/emoji.js)
  try{ if(window && typeof window.initEmojiPicker === 'function') window.initEmojiPicker(); }catch(e){}

  // initialize file attachment UI (extracted to static/app/attachments.js)
  try{ if(window && typeof window.initFileAttachments === 'function') window.initFileAttachments(); }catch(e){}

  // reply cancel
  const replyCancel = document.getElementById('reply-cancel');
  if(replyCancel){
    replyCancel.addEventListener('click', ()=>{
      const rp = document.getElementById('reply-preview'); if(rp) rp.style.display='none';
      const composerEl = document.getElementById('composer'); delete composerEl.dataset.replyTo;
    });
  }

  // helper: delegate to extracted API module if present
  async function fetchJSON(url, opts){
    try{ if(window && typeof window.fetchJSON === 'function') return await window.fetchJSON(url, opts); }catch(e){}
    // fallback minimal implementation
    try{ opts = opts || {}; if(typeof opts.credentials === 'undefined') opts.credentials = 'include'; opts.headers = opts.headers || {}; const r = await fetch(url, opts); if(!r.ok) return null; return await r.json().catch(()=>null); }catch(e){ console.warn('fetchJSON fallback failed', e); return null; }
  }

  // delegate to extracted rooms module when available
  async function loadRooms(){ try{ if(window && typeof window.loadRooms === 'function') return await window.loadRooms(); }catch(e){} }

  async function loadContacts(){ try{ if(window && typeof window.loadContacts === 'function') return await window.loadContacts(); }catch(e){} }

  async function loadRoomMembers(roomId){ try{ if(window && typeof window.loadRoomMembers === 'function') return await window.loadRoomMembers(roomId); }catch(e){} }

  async function loadRoomMessages(roomId, opts){ try{ if(window && typeof window.loadRoomMessages === 'function') return await window.loadRoomMessages(roomId, opts); }catch(e){} }

  async function loadDialogMessages(otherId, opts){ try{ if(window && typeof window.loadDialogMessages === 'function') return await window.loadDialogMessages(otherId, opts); }catch(e){} }

  // bootstrap loader moved to static/app/bootstrap.js
  try{ if(window && typeof window.bootstrap === 'function') window.bootstrap(); }catch(e){}

  // simple escape for username rendering
  function escapeHtml(str){
    return String(str).replace(/[&<>"']/g, (s)=>({ '&':'&amp;', '<':'&lt;', '>':'&gt;', '"':'&quot;', "'":"&#39;" }[s]));
  }

  // Minimal shims that delegate to the rooms module. Keeping tiny shims here preserves
  // compatibility when scripts load in different orders and keeps app.js small.
  function selectRoom(roomOrId){ try{ if(window && window.roomsApi && typeof window.roomsApi.selectRoom === 'function') return window.roomsApi.selectRoom(roomOrId); if(window && typeof window.selectRoom === 'function' && window.selectRoom !== selectRoom) return window.selectRoom(roomOrId); }catch(e){}
    // best-effort fallback: set currentRoom and call generic loader
    try{
      let room = roomOrId;
      if(!room) return;
      if(typeof roomOrId === 'number' || typeof roomOrId === 'string'){
        room = (window.rooms||[]).find(r => String(r.id) === String(roomOrId)) || { id: roomOrId };
      }
      window.currentRoom = room;
      window.isDialog = !!room.is_dialog || false;
      try{ if(roomTitle) roomTitle.textContent = room.name || room.other_name || (window.isDialog ? 'Dialog' : 'Room'); }catch(e){}
      try{ if(window.messagesEl) window.messagesEl.innerHTML = ''; }catch(e){}
      try{ if(window.isDialog) loadDialogMessages(room.id); else loadRoomMessages(room.id); }catch(e){}
    }catch(e){}
  }

  function openDialog(otherId){ try{ if(window && window.roomsApi && typeof window.roomsApi.selectRoom === 'function') return window.roomsApi.selectRoom({ id: otherId, other_id: otherId, is_dialog: true, name: null }); return selectRoom({ id: otherId, other_id: otherId, is_dialog: true, name: null }); }catch(e){} }

  function renderRooms(){ try{ if(window && window.roomsApi && typeof window.roomsApi.renderRooms === 'function') return window.roomsApi.renderRooms(); }catch(e){}
    try{ if(!roomsList) return; roomsList.innerHTML = ''; (window.rooms||[]).forEach(r=>{ const li = document.createElement('li'); li.dataset.id = String(r.id); li.textContent = r.name || ('room'+r.id); li.addEventListener('click', ()=> selectRoom(r)); roomsList.appendChild(li); }); }catch(e){} }

  function renderContacts(){ try{ if(window && window.roomsApi && typeof window.roomsApi.renderContacts === 'function') return window.roomsApi.renderContacts(); }catch(e){}
    try{ if(!contactsList) return; contactsList.innerHTML = ''; (window.contacts||[]).forEach(c=>{ const li = document.createElement('li'); li.dataset.id = String(c.id); li.textContent = c.name || ('user'+c.id); li.addEventListener('click', ()=> openDialog(c.id)); contactsList.appendChild(li); }); }catch(e){} }

  function renderMembers(membersArr){ try{ if(window && window.roomsApi && typeof window.roomsApi.renderMembers === 'function') return window.roomsApi.renderMembers(membersArr); }catch(e){}
    try{ if(!membersList) return; membersList.innerHTML = ''; (membersArr||[]).forEach(m=>{ const li = document.createElement('li'); li.textContent = `${m.name || m.id}${m.online ? ' (online)' : ''}`; membersList.appendChild(li); }); }catch(e){} }

  // delegate to centralized UI helpers (if the new ui.js is present it exposes window.showModal/window.showToast)
  function showModal(opts){
    try{ if(window && typeof window.showModal === 'function') return window.showModal(opts); }catch(e){}
    // fallback: simple confirm-like Promise
    return new Promise((resolve)=>{ try{ const ok = confirm(opts && opts.body ? opts.body : (opts && opts.title) || 'Confirm?'); resolve(Boolean(ok)); }catch(e){ resolve(false); } });
  }

  function showToast(msg, type='success', timeout=3000){
    try{ if(window && typeof window.showToast === 'function'){ return window.showToast(msg, type, timeout); } }catch(e){}
    // fallback minimal implementation
    try{ const rt = document.getElementById('toast-root') || (function(){ const r=document.createElement('div'); r.id='toast-root'; document.body.appendChild(r); return r; })(); const cont = rt.querySelector('.toast-container') || (function(){ const c=document.createElement('div'); c.className='toast-container'; rt.appendChild(c); return c; })(); const t = document.createElement('div'); t.className='toast'; t.textContent = msg; cont.appendChild(t); setTimeout(()=>t.remove(), timeout); }catch(e){ console.warn('showToast fallback failed', msg); }
  }

  // wire logout button
  const logoutBtn = document.getElementById('btn-logout');
  if(logoutBtn){
    logoutBtn.addEventListener('click', async ()=>{
      try{
        await fetch('/logout', {method:'POST', credentials:'include'});
      }catch(e){}
      // redirect to login page
  location.href = '/static/auth/login.html';
    });
  }

  // expose UI hooks for extracted modules (rooms.js expects these on window)
  try{ window.selectRoom = selectRoom; window.openDialog = openDialog; window.renderRooms = renderRooms; window.renderContacts = renderContacts; window.renderMembers = renderMembers; }catch(e){}
  bootstrap();

  roomsToggle.addEventListener('click', ()=>{
    roomsSection.classList.toggle('compacted');
  });
});
