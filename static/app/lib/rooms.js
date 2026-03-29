// Minimal rooms UI script used by /static/rooms/index.html
(function(){
  async function fetchRooms(q, limit, offset){
    q = q || '';
    limit = typeof limit === 'number' ? limit : 10;
    offset = typeof offset === 'number' ? offset : 0;
    try{
      const params = new URLSearchParams();
      if(q) params.append('q', q);
      // include visibility filter if present in the DOM
      try{ const visEl = document.getElementById('rooms-visibility'); if(visEl && visEl.value) params.append('visibility', visEl.value); }catch(e){}
      params.append('limit', String(limit));
      params.append('offset', String(offset));
      const r = await fetch('/rooms?' + params.toString());
      if(r.status !== 200) return { rooms: [], total: 0 };
      const data = await r.json().catch(()=>null);
      // server returns { rooms: [...] }
      return { rooms: data && data.rooms ? data.rooms : [], total: (data && data.total) ? data.total : null };
    }catch(e){ console.warn('fetchRooms failed', e); return { rooms: [], total: 0 }; }
  }

  async function renderRooms(){
    try{
      const container = document.getElementById('rooms-list'); if(!container) return;
      container.innerHTML = '<div style="color:var(--muted)">Loading…</div>';
      // read current search/pagination state from DOM
  const searchEl = document.getElementById('rooms-search');
  const paginationEl = document.getElementById('rooms-pagination');
  const pageSizeEl = document.getElementById('rooms-page-size');
  const q = searchEl ? (searchEl.value || '') : '';
  const vis = (document.getElementById('rooms-visibility') || {}).value || 'public';
  const limit = pageSizeEl ? parseInt(pageSizeEl.value || '10') : 10;
      const offset = parseInt(paginationEl && paginationEl.getAttribute('data-offset')) || 0;

      const resp = await fetchRooms(q, limit, offset);
      const rooms = resp.rooms || [];
      const total = resp.total;
      if(!rooms || rooms.length === 0){ container.innerHTML = '<div class="admin-empty">No rooms</div>'; // still render pagination area
        renderPagination(total, limit, offset);
        return; }
      // update heading to indicate current visibility filter
      try{ const heading = document.getElementById('rooms-list-heading'); if(heading){ heading.textContent = (vis === 'public') ? 'Public rooms' : (vis === 'private' ? 'Private rooms (mine)' : 'All rooms'); } }catch(e){}
      const ul = document.createElement('ul'); ul.style.listStyle='none'; ul.style.padding='0'; ul.style.margin='0';
      rooms.forEach(r=>{
        const li = document.createElement('li'); li.style.padding='10px'; li.style.border='1px solid #f3f6fb'; li.style.marginBottom='8px'; li.style.borderRadius='8px';
        // ensure each li has a data-id so selection and unread-badge lookups work
        try{ li.dataset.id = String(r.id); }catch(e){}
        // make the room title a clickable link that selects the room or navigates to chat page
        const titleLink = document.createElement('a');
        titleLink.href = `/static/chat/index.html?room=${encodeURIComponent(r.id)}`;
        titleLink.style.fontWeight = '700';
        titleLink.style.color = 'inherit';
        titleLink.style.textDecoration = 'none';
        titleLink.textContent = r.name || ('room'+r.id);
        titleLink.addEventListener('click', (ev)=>{
          try{
            // Prefer to open room details in the shared modal when clicking on a room in the rooms index.
            // Load the shared UI if necessary and call selectRoom which will render a modal when available.
            const onRoomsPath = (typeof location !== 'undefined' && location.pathname && String(location.pathname).indexOf('/static/rooms') !== -1);
            // Only intercept when we're on the rooms index or when a messages container exists (in-page selection).
            const messagesEl = document.querySelector && document.querySelector('#messages');
            const hasMessages = !!(messagesEl && messagesEl.parentElement);
            if(window && typeof window.selectRoom === 'function' && (onRoomsPath || hasMessages)){
              ev.preventDefault();
              (async ()=>{
                try{
                  // ensure UI modal helper is loaded so renderRoomDetails will use a modal
                  if(window && typeof window.showModal !== 'function'){
                    try{
                      await new Promise((resolve)=>{
                        const s = document.createElement('script'); s.async = true; s.src = '/static/app/ui/ui.js?_=' + Date.now(); s.onload = ()=>{ setTimeout(()=>resolve(), 0); }; s.onerror = ()=>{ resolve(); }; document.head.appendChild(s);
                      });
                    }catch(e){}
                  }
                  try{ window.selectRoom(r); }catch(e){}
                }catch(e){}
              })();
            }
          }catch(e){ /* allow navigation on error */ }
        });
        const title = titleLink;
        const desc = document.createElement('div'); desc.style.color='var(--muted)'; desc.style.fontSize='13px'; desc.textContent = r.description || '';
  // meta: left side for actions/count, right side for owner/visibility
  const meta = document.createElement('div'); meta.style.marginTop='8px'; meta.style.display='flex'; meta.style.gap='8px'; meta.style.alignItems='center'; meta.style.justifyContent='space-between';
  const metaLeft = document.createElement('div'); metaLeft.style.display = 'inline-flex'; metaLeft.style.gap = '8px'; metaLeft.style.alignItems = 'center';
  const metaRight = document.createElement('div'); metaRight.style.display = 'inline-flex'; metaRight.style.flexDirection = 'column'; metaRight.style.alignItems = 'flex-end'; metaRight.style.gap = '4px';
  const joinBtn = document.createElement('button'); joinBtn.className='btn-join'; joinBtn.textContent='Join';
  const leaveBtn = document.createElement('button'); leaveBtn.className='btn-leave'; leaveBtn.textContent='Leave'; leaveBtn.style.display='none';

        // Initialize button visibility from server-provided flag `is_member` when available.
        try{
          if(r && r.is_member || r && r.owner_id && window.currentUserId && String(r.owner_id) === String(window.currentUserId)){
            joinBtn.style.display = 'none';
            leaveBtn.style.display = 'inline-flex';
          } else {
            joinBtn.style.display = 'inline-flex';
            leaveBtn.style.display = 'none';
          }
        }catch(e){}

        // If the current user is banned from this room, hide join/leave and show a banned badge.
        try{
          if(r && r.is_banned){
            joinBtn.style.display = 'none';
            leaveBtn.style.display = 'none';
            if(!metaLeft.querySelector('.banned-badge')){
              const bannedBadge = document.createElement('span');
              bannedBadge.className = 'banned-badge';
              bannedBadge.style.cssText = 'color:#c0392b;font-weight:600;font-size:.85em;padding:4px 8px;background:#fdecea;border-radius:6px;border:1px solid #e57373;white-space:nowrap;';
              bannedBadge.textContent = '🚫 Banned';
              metaLeft.appendChild(bannedBadge);
            }
          }
        }catch(e){}

        // Ensure the shared UI helpers are available. Prefer the shared modal
        // frame (window.showModal) by loading the ui bundle if necessary. Only
        // fall back to confirm() if the shared modal cannot be loaded for some
        // reason (keeps test envs working).
        async function ensureUi(){
          try{
            if(window && typeof window.showModal === 'function') return;
            // Dynamically load the UI module with a cache-busting timestamp.
            return new Promise((resolve)=>{
              try{
                const s = document.createElement('script');
                s.async = true;
                s.src = '/static/app/ui/ui.js?_=' + Date.now();
                s.onload = ()=>{ setTimeout(()=>resolve(), 0); };
                s.onerror = ()=>{ resolve(); };
                document.head.appendChild(s);
              }catch(e){ resolve(); }
            });
          }catch(e){}
        }

        joinBtn.addEventListener('click', async ()=>{
          try{
            await ensureUi();
            const confirmOpts = { title: 'Join room', body: (r.name ? `Join room "${r.name}"?` : 'Join this room?'), confirmText: 'Join', cancelText: 'Cancel' };
            let ok = true;
            try{
              if(window && typeof window.showModal === 'function'){
                ok = await window.showModal(confirmOpts);
              } else {
                // last-resort fallback if the shared UI couldn't be loaded
                ok = window.confirm(confirmOpts.body);
              }
            }catch(e){ ok = true; }
            if(!ok) return;
            showStatus && showStatus('Joining…');
            const j = await fetch('/rooms/' + r.id + '/join', { method:'POST', credentials:'include', headers: authHeaders('application/json') });
            if(j.status === 200){
              const jb = await j.json().catch(()=>null);
              if(jb && jb.already_member){
                showToast && showToast('You are already a member of this room', 'info');
              } else {
                showToast && showToast('Joined room','success');
              }
              joinBtn.style.display = 'none';
              leaveBtn.style.display = 'inline-flex';
              renderRooms();
            } else {
              const body = await j.json().catch(()=>null);
              showToast && showToast('Failed to join: ' + JSON.stringify(body),'error');
            }
          }catch(e){ console.warn('join failed', e); showToast && showToast('Join failed','error'); }
        });

        leaveBtn.addEventListener('click', async ()=>{
          try{
            // Ask for confirmation via shared modal (load UI if needed)
            try{ await ensureUi(); }catch(e){}
            const confirmOpts = { title: 'Leave room', body: (r.name ? `Leave room "${r.name}"?` : 'Leave this room?'), confirmText: 'Leave', cancelText: 'Cancel' };
            let ok = true;
            try{
              if(window && typeof window.showModal === 'function'){
                ok = await window.showModal(confirmOpts);
              } else {
                ok = window.confirm(confirmOpts.body);
              }
            }catch(e){ ok = true; }
            if(!ok) return;
            showStatus && showStatus('Leaving…');
            const l = await fetch('/rooms/' + r.id + '/leave', { method:'POST', credentials:'include', headers: authHeaders('application/json') });
            if(l.status === 200){
              showToast && showToast('Left room','success');
              // swap buttons
              leaveBtn.style.display = 'none';
              joinBtn.style.display = 'inline-flex';
              renderRooms();
            } else {
              const body = await l.json().catch(()=>null);
              showToast && showToast('Failed to leave: ' + JSON.stringify(body),'error');
            }
          }catch(e){ console.warn('leave failed', e); showToast && showToast('Leave failed','error'); }
        });

        metaLeft.appendChild(joinBtn);
        metaLeft.appendChild(leaveBtn);
        const count = document.createElement('div'); count.style.color='var(--muted)'; count.textContent = (r.member_count || 0) + ' members'; metaLeft.appendChild(count);
        // show owner, admins, members and visibility in the right column; truncate long owner names and add small initials avatar
        try{
          const ownerWrap = document.createElement('div'); ownerWrap.style.display = 'inline-flex'; ownerWrap.style.alignItems = 'center'; ownerWrap.style.gap = '6px';
          const avatar = document.createElement('div'); avatar.style.width = '28px'; avatar.style.height = '28px'; avatar.style.borderRadius = '50%'; avatar.style.background = 'var(--muted-light)'; avatar.style.display = 'inline-flex'; avatar.style.alignItems = 'center'; avatar.style.justifyContent = 'center'; avatar.style.color = 'white'; avatar.style.fontSize = '12px'; avatar.style.flex = '0 0 auto';
          const ownerSmall = document.createElement('div'); ownerSmall.style.color='var(--muted)'; ownerSmall.style.fontSize='12px'; ownerSmall.style.maxWidth='160px'; ownerSmall.style.overflow='hidden'; ownerSmall.style.whiteSpace='nowrap'; ownerSmall.style.textOverflow='ellipsis'; ownerSmall.style.textAlign='right';
          let ownerLabel = '';
          try{
            const ownerObj = r.owner_obj || (r.owner && typeof r.owner === 'object' ? r.owner : null);
            const ownerId = (r.owner && typeof r.owner !== 'object') ? r.owner : r.owner_id;
            ownerLabel = (ownerObj && (ownerObj.display_name || ownerObj.username || ownerObj.name)) || (ownerId ? String(ownerId) : '—');
            // compute initials for avatar
            const nameForInitials = ownerObj && (ownerObj.display_name || ownerObj.username || ownerObj.name) ? (ownerObj.display_name || ownerObj.username || ownerObj.name) : (ownerId ? String(ownerId) : '');
            const initials = nameForInitials.split(/\s+/).map(s=>s[0]).join('').slice(0,2).toUpperCase();
            avatar.textContent = initials || '?';
          }catch(e){ ownerLabel = (r.owner || r.owner_id) ? String(r.owner || r.owner_id) : '—'; avatar.textContent = '?'; }
          ownerSmall.textContent = 'Owner: ' + ownerLabel;
          ownerWrap.appendChild(avatar);
          ownerWrap.appendChild(ownerSmall);
          metaRight.appendChild(ownerWrap);
        }catch(e){}
        try{
          // admins list (show up to 3 names)
          try{
            const adminsArr = r.admins_info || r.admins || [];
            let adminNames = [];
            if(Array.isArray(adminsArr)){
              adminNames = adminsArr.slice(0,3).map(a => (a && (a.display_name || a.username || a.name)) || String(a)).filter(Boolean);
            }
            const adminsSmall = document.createElement('div'); adminsSmall.style.color='var(--muted)'; adminsSmall.style.fontSize='12px'; adminsSmall.style.textAlign='right';
            adminsSmall.textContent = adminNames.length ? ('Admins: ' + adminNames.join(', ')) : 'Admins: —';
            metaRight.appendChild(adminsSmall);
          }catch(e){}

          // members count (already shown left; repeat here for clarity)
          try{
            const membersSmall = document.createElement('div'); membersSmall.style.color='var(--muted)'; membersSmall.style.fontSize='12px'; membersSmall.style.textAlign='right';
            membersSmall.textContent = 'Members: ' + (r.member_count || 0);
            metaRight.appendChild(membersSmall);
          }catch(e){}

          // banned count (if available)
          try{
            const bannedSmall = document.createElement('div'); bannedSmall.style.color='var(--muted)'; bannedSmall.style.fontSize='12px'; bannedSmall.style.textAlign='right';
            const bannedCount = (typeof r.banned_count === 'number') ? r.banned_count : (r.bans ? r.bans.length : 0);
            bannedSmall.textContent = 'Banned: ' + (bannedCount || 0);
            metaRight.appendChild(bannedSmall);
          }catch(e){}

          const visSmall = document.createElement('div'); visSmall.style.color='var(--muted)'; visSmall.style.fontSize='12px'; visSmall.textContent = 'Visibility: ' + (r.visibility || 'public');
          metaRight.appendChild(visSmall);
        }catch(e){}
        meta.appendChild(metaLeft);
        meta.appendChild(metaRight);
        li.appendChild(title); if(desc.textContent) li.appendChild(desc); li.appendChild(meta); ul.appendChild(li);
      });
      container.innerHTML = '';
      container.appendChild(ul);
      renderPagination(total, limit, offset);
    }catch(e){ console.warn('renderRooms failed', e); }
  }

  function renderPagination(total, limit, offset){
    try{
      const paginationEl = document.getElementById('rooms-pagination'); if(!paginationEl) return;
      paginationEl.innerHTML = '';
      paginationEl.setAttribute('data-offset', String(offset || 0));
  const prev = document.createElement('button'); prev.textContent = 'Prev'; prev.className = 'btn'; prev.disabled = offset <= 0;
  const next = document.createElement('button'); next.textContent = 'Next'; next.className = 'btn';
      // if total is known, disable next when we've reached the end
      if(typeof total === 'number'){
        next.disabled = offset + limit >= total;
      }
  prev.addEventListener('click', ()=>{ const newOffset = Math.max(0, offset - limit); paginationEl.setAttribute('data-offset', String(newOffset)); renderRooms(); });
  next.addEventListener('click', ()=>{ const newOffset = offset + limit; paginationEl.setAttribute('data-offset', String(newOffset)); renderRooms(); });
      paginationEl.appendChild(prev);
      const info = document.createElement('div'); info.style.color='var(--muted)'; info.style.fontSize='13px'; info.textContent = (typeof total === 'number') ? `${Math.min(offset+1, total)}-${Math.min(offset+limit, total)} of ${total}` : `offset ${offset+1}`;
      paginationEl.appendChild(info);
      paginationEl.appendChild(next);
    }catch(e){}
  }

  async function createRoom(name, visibility, description){
    try{
      const payload = { name, visibility };
      if(typeof description !== 'undefined') payload.description = description;
      const r = await fetch('/rooms', { method:'POST', credentials:'include', headers: authHeaders('application/json'), body: JSON.stringify(payload) });
      if(r.status === 200){ const data = await r.json().catch(()=>null); showToast && showToast('Room created','success'); renderRooms(); return data && data.room; }
      else { const body = await r.json().catch(()=>null); showToast && showToast('Failed to create: ' + JSON.stringify(body),'error'); return null; }
    }catch(e){ console.warn('createRoom failed', e); showToast && showToast('Failed to create room','error'); return null; }
  }

  // wire up page handlers when the DOM is ready
  function attach(){
    try{
      const btn = document.getElementById('btn-create-room');
      if(btn){
        btn.onclick = async ()=>{
          try{
            btn.disabled = true;
          const name = (document.getElementById('new-room-name') || {}).value || '';
          const desc = (document.getElementById('new-room-description') || {}).value || '';
          const vis = (document.getElementById('new-room-visibility') || {}).value || 'public';
            if(!name) return showToast && showToast('enter a room name','error');

            // ensure the shared UI modal exists
            async function ensureUiLocal(){
              try{ if(window && typeof window.showModal === 'function') return; return new Promise((resolve)=>{ try{ const s = document.createElement('script'); s.async = true; s.src = '/static/app/ui/ui.js?_=' + Date.now(); s.onload = ()=>{ setTimeout(()=>resolve(), 0); }; s.onerror = ()=>{ resolve(); }; document.head.appendChild(s); }catch(e){ resolve(); } }); }catch(e){}
            }

            await ensureUiLocal();
            const confirmOpts = { title: 'Create room', body: `Create room "${name}" (${vis})?`, confirmText: 'Create', cancelText: 'Cancel' };
            let ok = true;
            try{
              if(window && typeof window.showModal === 'function'){
                ok = await window.showModal(confirmOpts);
              } else {
                ok = window.confirm(confirmOpts.body);
              }
            }catch(e){ ok = true; }
            if(!ok) return;

          await createRoom(name, vis, desc);
          }catch(e){ console.warn('createRoom handler failed', e); showToast && showToast('Failed to create room','error'); }
          finally{ btn.disabled = false; }
        };
      }
      // wire up search debounce and page-size change
      try{
        const search = document.getElementById('rooms-search');
        const pageSize = document.getElementById('rooms-page-size');
        let debounceTimer = null;
        if(search){
          search.addEventListener('input', ()=>{
            if(debounceTimer) clearTimeout(debounceTimer);
            debounceTimer = setTimeout(()=>{ const paginationEl = document.getElementById('rooms-pagination'); if(paginationEl) paginationEl.setAttribute('data-offset', '0'); renderRooms(); }, 250);
          });
        }
        if(pageSize){
          pageSize.addEventListener('change', ()=>{ const paginationEl = document.getElementById('rooms-pagination'); if(paginationEl) paginationEl.setAttribute('data-offset', '0'); renderRooms(); });
        }
          // visibility filter change
          try{
            const vis = document.getElementById('rooms-visibility');
            if(vis){ vis.addEventListener('change', ()=>{ const paginationEl = document.getElementById('rooms-pagination'); if(paginationEl) paginationEl.setAttribute('data-offset', '0'); renderRooms(); }); }
          }catch(e){}
      }catch(e){}
    }catch(e){}
    renderRooms();
  }

  try{ document.addEventListener('DOMContentLoaded', attach); }catch(e){ try{ attach(); }catch(e){} }
  // Render the details panel for a selected room. Exposed as window.selectRoom
  async function renderRoomDetails(r){
    try{
      const panel = document.getElementById('room-details'); if(!panel) return;
  // If the passed room object lacks detailed lists/owner (or richer info), fetch full details
  let room = r || {};
  const hasRich = room && (room.owner_obj || room.admins_info || room.members_info || room.bans_info);
  // if we don't already have richer info and we only have a lightweight room object with an id, fetch details
  const needsFetch = !hasRich && room && room.id;
    if(needsFetch){
        try{
          const dr = await fetch('/rooms/' + room.id, { credentials: 'include', headers: authHeaders('application/json') });
          if(dr && dr.status === 200){ const data = await dr.json().catch(()=>null); room = (data && data.room) ? data.room : (data || room); }
        }catch(e){ /* ignore fetch errors and fall back to provided object */ }
      }

  // determine current user id (try window.appState.user first, otherwise request /me)
  try{
    let currentUserId = null;
    try{ if(window && window.appState && window.appState.user && window.appState.user.id) currentUserId = window.appState.user.id; }catch(e){}
    if(!currentUserId){
      try{
        // try sessionStorage boot_user (header/bootstrap may place user there)
        try{ const bs = sessionStorage && sessionStorage.getItem && sessionStorage.getItem('boot_user'); if(bs){ const bobj = JSON.parse(bs); if(bobj && bobj.id) currentUserId = bobj.id; } }catch(e){}
      }catch(e){}
      if(!currentUserId){
        try{
          const me = await fetch('/me', { credentials: 'include' });
          if(me && me.status === 200){ const mb = await me.json().catch(()=>null); if(mb && mb.user && (mb.user.id || mb.user.id === 0)) currentUserId = mb.user.id; }
        }catch(e){}
      }
    }
    if(currentUserId){
      try{ room.is_owner = (room.owner_id && String(room.owner_id) === String(currentUserId)); }catch(e){ room.is_owner = false; }
      try{
        if(Array.isArray(room.admins)) room.is_admin = room.admins.map(a=>String(a)).indexOf(String(currentUserId)) !== -1;
        else if(Array.isArray(room.admins_info)) room.is_admin = room.admins_info.map(a=>String((a && (a.id || a.user_id)) || a)).indexOf(String(currentUserId)) !== -1;
        else room.is_admin = false;
      }catch(e){ room.is_admin = false; }
    } else {
      room.is_owner = !!room.is_owner;
      room.is_admin = !!room.is_admin;
    }
    // debug: expose computed user and role flags
    try{ if(typeof window !== 'undefined' && window.ROOMS_DEBUG){ try{ console.debug('renderRoomDetails: currentUserId=', currentUserId); }catch(e){} try{ console.debug('renderRoomDetails: room.is_owner=', !!room.is_owner, 'room.is_admin=', !!room.is_admin); }catch(e){} } }catch(e){}
  }catch(e){}

  // If the shared modal is available, render the room details inside a modal
  if(typeof window !== 'undefined' && typeof window.showModal === 'function'){
    try{
      // small helper to build list elements
      function makeListEl(items){ const ul = document.createElement('ul'); ul.style.margin='0'; ul.style.paddingLeft='18px'; ul.style.color='var(--muted)'; if(!items || items.length === 0){ const li = document.createElement('li'); li.textContent = '—'; ul.appendChild(li); return ul; } items.forEach(u=>{ const li = document.createElement('li'); let label = ''; try{ if(u && (u.display_name || u.name)) label = u.display_name || u.name; else if(u && u.username) label = u.username; else if(typeof u === 'number' || (u && typeof u.id !== 'undefined')) label = (u && (u.username || u.id)) || String(u); else label = String(u); }catch(e){ label = String(u); } li.textContent = label; li._user = u; ul.appendChild(li); }); return ul; }

      const container = document.createElement('div'); container.style.maxWidth = '920px';
      const grid = document.createElement('div'); grid.style.display = 'grid'; grid.style.gridTemplateColumns = '1fr 320px'; grid.style.gap = '16px';

      const left = document.createElement('div');
      // Name
      const nameWrap = document.createElement('div'); nameWrap.style.marginBottom='8px';
      const nameLabel = document.createElement('label'); nameLabel.style.fontWeight='600'; nameLabel.textContent = 'Name'; nameWrap.appendChild(nameLabel);
      const nameVal = document.createElement('div'); nameVal.style.padding='8px'; nameVal.style.border='1px solid #e6e9ef'; nameVal.style.borderRadius='6px'; nameVal.style.marginTop='6px'; nameVal.textContent = room.name || ('room' + room.id); nameWrap.appendChild(nameVal);
      left.appendChild(nameWrap);

      // Description
      const descWrap = document.createElement('div'); descWrap.style.marginBottom='8px'; const descLabel = document.createElement('label'); descLabel.style.fontWeight='600'; descLabel.textContent='Description'; descWrap.appendChild(descLabel); const descVal = document.createElement('div'); descVal.style.padding='8px'; descVal.style.border='1px solid #e6e9ef'; descVal.style.borderRadius='6px'; descVal.style.marginTop='6px'; descVal.style.minHeight='48px'; descVal.textContent = room.description || '—'; descWrap.appendChild(descVal); left.appendChild(descWrap);

      // Visibility
      const visWrap = document.createElement('div'); visWrap.style.marginBottom='8px'; const visLabel = document.createElement('label'); visLabel.style.fontWeight='600'; visLabel.textContent='Visibility'; visWrap.appendChild(visLabel); const visVal = document.createElement('div'); visVal.style.padding='8px'; visVal.style.border='1px solid #e6e9ef'; visVal.style.borderRadius='6px'; visVal.style.marginTop='6px'; visVal.textContent = room.visibility || 'public'; visWrap.appendChild(visVal); left.appendChild(visWrap);

      // Owner
      const ownerWrap = document.createElement('div'); ownerWrap.style.marginBottom='8px'; const ownerLabel = document.createElement('label'); ownerLabel.style.fontWeight='600'; ownerLabel.textContent='Owner'; ownerWrap.appendChild(ownerLabel); const ownerVal = document.createElement('div'); ownerVal.style.padding='8px'; ownerVal.style.border='1px solid #e6e9ef'; ownerVal.style.borderRadius='6px'; ownerVal.style.marginTop='6px'; const ownerObj = room.owner_obj || (room.owner && typeof room.owner === 'object' ? room.owner : null); const ownerId = (room.owner && typeof room.owner !== 'object') ? room.owner : room.owner_id; ownerVal.textContent = (ownerObj && (ownerObj.display_name || ownerObj.name || ownerObj.username)) || (ownerId ? String(ownerId) : '—'); ownerWrap.appendChild(ownerVal); left.appendChild(ownerWrap);

      const right = document.createElement('div');
      // Admins
      const adminsSection = document.createElement('div'); adminsSection.style.marginBottom='12px'; const adminsLabel = document.createElement('label'); adminsLabel.style.fontWeight='600'; adminsLabel.textContent='Admins'; adminsSection.appendChild(adminsLabel); const adminsList = makeListEl(room.admins_info || (room.admins || []).map(id=>({ id }))); adminsList.style.marginTop='6px'; adminsSection.appendChild(adminsList); right.appendChild(adminsSection);

      // Members
      const membersSection = document.createElement('div'); membersSection.style.marginBottom='12px'; const membersLabel = document.createElement('label'); membersLabel.style.fontWeight='600'; membersLabel.textContent='Members'; membersSection.appendChild(membersLabel); const membersList = makeListEl(room.members_info || (room.members || []).map(id=>({ id }))); membersList.style.marginTop='6px'; membersList.style.maxHeight='160px'; membersList.style.overflow='auto'; membersList.style.border='1px solid #f3f5f8'; membersList.style.padding='8px'; membersList.style.borderRadius='6px'; membersSection.appendChild(membersList); right.appendChild(membersSection);

      // Banned
      const bannedSection = document.createElement('div'); const bannedLabel = document.createElement('label'); bannedLabel.style.fontWeight='600'; bannedLabel.textContent='Banned users '; const bannedCountSpan = document.createElement('span'); bannedCountSpan.id = 'room-banned-count'; bannedCountSpan.style.fontWeight='600'; bannedCountSpan.style.color='var(--muted)'; bannedCountSpan.style.marginLeft='8px'; bannedCountSpan.textContent = String((room.bans_info || (room.bans || room.banned || [])).length || 0); bannedLabel.appendChild(bannedCountSpan); bannedSection.appendChild(bannedLabel); const bannedList = makeListEl(room.bans_info || (room.bans || room.banned || []).map(id=>({ id }))); bannedList.style.marginTop='6px'; bannedList.style.maxHeight='160px'; bannedList.style.overflow='auto'; bannedList.style.border='1px solid #f3f5f8'; bannedList.style.padding='8px'; bannedList.style.borderRadius='6px'; bannedSection.appendChild(bannedList); right.appendChild(bannedSection);

      grid.appendChild(left); grid.appendChild(right); container.appendChild(grid);

      // actions row
      const actions = document.createElement('div'); actions.style.marginTop='12px'; actions.style.display='flex'; actions.style.gap='8px';
  const btnJoin = document.createElement('button'); btnJoin.id = 'btn-join-room'; btnJoin.className='btn'; btnJoin.textContent='Join';
  const btnLeave = document.createElement('button'); btnLeave.id = 'btn-leave-room'; btnLeave.className='btn'; btnLeave.textContent='Leave'; btnLeave.style.display='none';
  const btnManage = document.createElement('button'); btnManage.id = 'btn-manage-room'; btnManage.className='btn btn-secondary'; btnManage.textContent='Manage'; btnManage.style.display = (room.is_owner || room.is_admin) ? 'inline-flex' : 'none';
  const btnGoToChat = document.createElement('button'); btnGoToChat.id = 'btn-go-to-chat'; btnGoToChat.className='btn'; btnGoToChat.textContent='Go to Chat';
  const btnDelete = document.createElement('button'); btnDelete.id = 'btn-delete-room'; btnDelete.className='btn btn-danger'; btnDelete.textContent='Delete'; btnDelete.style.display = (room.is_owner || room.is_admin) ? 'inline-flex' : 'none';
      actions.appendChild(btnJoin); actions.appendChild(btnLeave); actions.appendChild(btnManage); actions.appendChild(btnGoToChat); actions.appendChild(btnDelete);
      container.appendChild(actions);

      // initialize membership button visibility
      try{ if(room.is_member){ btnJoin.style.display='none'; btnLeave.style.display='inline-flex'; } else { btnJoin.style.display='inline-flex'; btnLeave.style.display='none'; } }catch(e){}

      // If the current user is banned, hide all action buttons and show a ban notice
      try{
        const isCurrentUserBanned = room.is_banned === true;
        if(isCurrentUserBanned){
          btnJoin.style.display = 'none';
          btnLeave.style.display = 'none';
          try{ btnGoToChat.style.display = 'none'; }catch(e){}
          try{ btnManage.style.display = 'none'; }catch(e){}
          try{ btnDelete.style.display = 'none'; }catch(e){}
          if(!container.querySelector('.ban-notice')){
            const banNotice = document.createElement('div');
            banNotice.className = 'ban-notice';
            banNotice.style.cssText = 'background:#fdecea;border:1px solid #e57373;border-radius:6px;color:#c0392b;font-weight:600;padding:10px 14px;margin-top:8px;display:flex;align-items:center;gap:8px;';
            const bannedByName = room.banned_by && (room.banned_by.username || room.banned_by.email);
            const bannedByText = bannedByName ? ` Banned by: ${bannedByName}.` : '';
            banNotice.innerHTML = `<span style="font-size:1.2em;">🚫</span><span>You have been banned from this room and cannot rejoin. Contact an admin to appeal.${bannedByText}</span>`;
            container.appendChild(banNotice);
          }
        }
      }catch(e){}

      // wire handlers (similar to inline behavior)
      btnJoin.addEventListener('click', async ()=>{
        try{ btnJoin.disabled = true; showStatus && showStatus('Joining…'); const j = await fetch('/rooms/' + room.id + '/join', { method:'POST', credentials:'include', headers: authHeaders('application/json') }); if(j.status === 200){ showToast && showToast('Joined room','success'); btnJoin.style.display='none'; btnLeave.style.display='inline-flex'; renderRooms(); } else { const body = await j.json().catch(()=>null); showToast && showToast('Failed to join: ' + JSON.stringify(body),'error'); } }catch(e){ console.warn('join failed', e); showToast && showToast('Join failed','error'); } finally{ btnJoin.disabled = false; } });

      btnLeave.addEventListener('click', async ()=>{
        try{ btnLeave.disabled = true; showStatus && showStatus('Leaving…'); const l = await fetch('/rooms/' + room.id + '/leave', { method:'POST', credentials:'include', headers: authHeaders('application/json') }); if(l.status === 200){ showToast && showToast('Left room','success'); btnLeave.style.display='none'; btnJoin.style.display='inline-flex'; renderRooms(); } else { const body = await l.json().catch(()=>null); showToast && showToast('Failed to leave: ' + JSON.stringify(body),'error'); } }catch(e){ console.warn('leave failed', e); showToast && showToast('Leave failed','error'); } finally{ btnLeave.disabled = false; } });

      btnDelete.addEventListener('click', async () => {
        btnDelete.disabled = true;
        try {
          const opts = {
            title: 'Delete room',
            body: (room.name ? `Delete room "${room.name}"? This cannot be undone.` : 'Delete this room? This cannot be undone.'),
            confirmText: 'Delete',
            cancelText: 'Cancel'
          };

          let ok = false;
          try {
            ok = await window.showModal(opts);
          } catch (e) {
            ok = window.confirm(opts.body);
          }
          if (!ok) return;

          const d = await fetch('/rooms/' + room.id, { method: 'DELETE', credentials: 'include', headers: authHeaders('application/json') });
          if (d && (d.status === 200 || d.status === 204)) {
            showToast && showToast('Room deleted', 'success');
            try {
              const li = document.querySelector('#rooms-list li[data-id="' + room.id + '"]');
              if (li && li.parentElement) li.parentElement.removeChild(li);
            } catch (e) { /* ignore */ }
            try { renderRooms(); } catch (e) { /* ignore */ }
            // modal remains open until user closes; nothing more to do here
          } else {
            const body = await d.json().catch(() => null);
            showToast && showToast('Failed to delete: ' + JSON.stringify(body), 'error');
          }
        } catch (e) {
          console.warn('delete failed', e);
          showToast && showToast('Delete failed', 'error');
        } finally {
          try { btnDelete.disabled = false; } catch (e) { /**/ }
        }
      });

      btnManage.addEventListener('click', async ()=>{
        try{
          // reuse existing manage UI creation from inline code path by calling the inline handler
          // Build same manage UI here
          const makeList = (items, emptyText='—')=>{
            const ul = document.createElement('ul'); ul.style.listStyle='none'; ul.style.padding='0'; ul.style.margin='0'; ul.style.display='grid'; ul.style.gap='6px';
            if(!items || items.length === 0){ const li = document.createElement('li'); li.style.color='var(--muted)'; li.textContent = emptyText; ul.appendChild(li); return ul; }
            items.forEach(item=>{
              const u = (item && typeof item === 'object') ? (item.id ? { id: item.id, display_name: item.display_name || item.username || item.name } : (item.name ? { id: Number(item.name), display_name: item.display_name || item.name } : { id: null, display_name: String(item) })) : { id: Number(item), display_name: String(item) };
              const li = document.createElement('li'); li.style.display='flex'; li.style.justifyContent='space-between'; li.style.alignItems='center';
              const name = document.createElement('span'); name.textContent = u.display_name || (u.id ? String(u.id) : '—');
              const actions = document.createElement('span'); actions.style.display='inline-flex'; actions.style.gap='6px';
              li.appendChild(name); li.appendChild(actions); li._user = u; ul.appendChild(li);
            });
            return ul;
          };

          const body = document.createElement('div'); body.style.display='grid'; body.style.gap='12px';
          const adminsSection = document.createElement('div'); const aH = document.createElement('h4'); aH.textContent = 'Admins'; adminsSection.appendChild(aH); const adminsList = makeList(room.admins_info || room.admins || []); adminsSection.appendChild(adminsList); body.appendChild(adminsSection);
          const membersSection = document.createElement('div'); const mH = document.createElement('h4'); mH.textContent = 'Members'; membersSection.appendChild(mH); const membersList = makeList(room.members_info || room.members || []); membersSection.appendChild(membersList); body.appendChild(membersSection);
          const messagesSection = document.createElement('div'); const msgH = document.createElement('h4'); msgH.textContent = 'Recent messages (admins may delete)'; messagesSection.appendChild(msgH); const messagesList = document.createElement('div'); messagesList.style.display='grid'; messagesList.style.gap='6px'; messagesList.style.maxHeight='220px'; messagesList.style.overflow='auto'; messagesList.style.border='1px solid #f3f5f8'; messagesList.style.padding='8px'; messagesSection.appendChild(messagesList); body.appendChild(messagesSection);
          const bannedSection = document.createElement('div'); const bH = document.createElement('h4'); bH.textContent = 'Banned users'; bannedSection.appendChild(bH); const bannedListModal = document.createElement('div'); bannedListModal.style.display='grid'; bannedListModal.style.gap='6px'; bannedListModal.style.maxHeight='180px'; bannedListModal.style.overflow='auto'; bannedListModal.style.border='1px solid #f3f5f8'; bannedListModal.style.padding='8px'; bannedSection.appendChild(bannedListModal); body.appendChild(bannedSection);

          // refresh helper: fetch room details, messages, and bans to populate lists
          async function refreshLists(){
            try{
              const dr = await fetch('/rooms/' + room.id, { credentials: 'include', headers: authHeaders('application/json') });
              if(dr && dr.status === 200){
                const data = await dr.json().catch(()=>null);
                const fresh = (data && data.room) ? data.room : null;
                if(fresh){
                  // rebuild admins/members lists
                  const newAdmins = makeList(fresh.admins_info || fresh.admins || []);
                  adminsSection.replaceChild(newAdmins, adminsList);
                  // members
                  const newMembers = makeList(fresh.members_info || fresh.members || []);
                  membersSection.replaceChild(newMembers, membersList);
                  // update references
                  // (note: reassigning local variables used by wireActions below is fine since we call wireActions after)
                }
              }
            }catch(e){ console.warn('refreshLists failed', e); }

            // fetch recent messages
            try{
              const mr = await fetch('/rooms/' + room.id + '/messages?limit=50', { credentials: 'include', headers: authHeaders('application/json') });
              messagesList.innerHTML = '';
              if(mr && mr.status === 200){ const mb = await mr.json().catch(()=>null); const msgs = (mb && mb.messages) || [];
                msgs.slice(-50).reverse().forEach(m=>{
                  const row = document.createElement('div'); row.style.display='flex'; row.style.justifyContent='space-between'; row.style.alignItems='center'; row.style.gap='8px';
                  const txt = document.createElement('div'); txt.style.flex='1'; txt.style.wordBreak='break-word'; txt.textContent = (m.display_name ? (m.display_name + ': ') : '') + (m.text || '');
                  const act = document.createElement('div'); act.style.display='inline-flex'; act.style.gap='6px';
                  const del = document.createElement('button'); del.className='btn'; del.textContent='Delete'; del.addEventListener('click', async ()=>{
                    try{ del.disabled = true; const d = await fetch('/rooms/' + room.id + '/messages/' + m.id, { method: 'DELETE', credentials: 'include', headers: authHeaders('application/json') }); if(d && d.status === 200){ showToast && showToast('Message deleted','success'); await refreshLists(); } else { const b = await d.json().catch(()=>null); showToast && showToast('Failed: '+JSON.stringify(b),'error'); } }catch(e){ console.warn('delete message failed', e); showToast && showToast('Failed','error'); } finally{ try{ del.disabled = false; }catch(e){} }
                  });
                  act.appendChild(del);
                  row.appendChild(txt); row.appendChild(act); messagesList.appendChild(row);
                });
              }
            }catch(e){ console.warn('load messages failed', e); }

            // fetch bans with banner info
            try{
              const br = await fetch('/rooms/' + room.id + '/bans', { credentials: 'include', headers: authHeaders('application/json') });
              bannedListModal.innerHTML = '';
              if(br && br.status === 200){ const bb = await br.json().catch(()=>null); const bans = (bb && bb.bans) || [];
                // fetch user names for banner and banned ids
                const ids = [];
                bans.forEach(bi => { if(bi.banned_id) ids.push(bi.banned_id); if(bi.banner_id) ids.push(bi.banner_id); });
                const uniq = Array.from(new Set(ids));
                let usersMap = {};
                if(uniq.length){ const q = '/users?ids=' + encodeURIComponent(uniq.join(',')); const ur = await fetch(q, { credentials: 'include' }); if(ur && ur.status === 200){ const ub = await ur.json().catch(()=>null); const users = (ub && ub.users) || []; users.forEach(u=>{ usersMap[u.id] = u; }); } }
                bans.forEach(bi=>{
                  const row = document.createElement('div'); row.style.display='flex'; row.style.justifyContent='space-between'; row.style.alignItems='center'; row.style.gap='8px';
                  const left = document.createElement('div'); left.style.flex='1';
                  const bannedName = (usersMap[bi.banned_id] && (usersMap[bi.banned_id].username || usersMap[bi.banned_id].email)) || String(bi.banned_id);
                  const bannerName = (usersMap[bi.banner_id] && (usersMap[bi.banner_id].username || usersMap[bi.banner_id].email)) || String(bi.banner_id || '—');
                  left.textContent = `${bannedName} (banned by ${bannerName})`;
                  const actions = document.createElement('div'); actions.style.display='inline-flex'; actions.style.gap='6px';
                  const unban = document.createElement('button'); unban.className='btn'; unban.textContent='Unban'; unban.addEventListener('click', async ()=>{ try{ unban.disabled = true; const res = await fetch('/rooms/' + room.id + '/unban', { method: 'POST', credentials: 'include', headers: Object.assign({'Content-Type':'application/json'}, authHeaders('application/json')), body: JSON.stringify({ user_id: bi.banned_id }) }); if(res && res.status === 200){ showToast && showToast('Unbanned','success'); await refreshLists(); } else { const b = await res.json().catch(()=>null); showToast && showToast('Failed: '+JSON.stringify(b),'error'); } }catch(e){ console.warn(e); showToast && showToast('Failed','error'); } finally{ try{ unban.disabled = false; }catch(e){} } });
                  actions.appendChild(unban);
                  row.appendChild(left); row.appendChild(actions); bannedListModal.appendChild(row);
                });
              }
            }catch(e){ console.warn('load bans failed', e); }
          }

          function wireActions(){
            // admins: demote (except owner)
            Array.from(adminsList.querySelectorAll('li')).forEach(li=>{
              const u = li._user; let actions = li.querySelector('span:last-child');
              if(!actions){ actions = document.createElement('span'); actions.style.display='inline-flex'; actions.style.gap='6px'; li.appendChild(actions); }
              actions.innerHTML = '';
              if(!u) return; // nothing to do for empty list items
              const rawId = (typeof u.id !== 'undefined' ? u.id : (typeof u.user_id !== 'undefined' ? u.user_id : u.name));
              const uid = (typeof rawId !== 'undefined' && rawId !== null && rawId !== '') ? Number(rawId) : null;
              if(!uid) return;
              const ownerIdForCompare = (room.owner_obj && room.owner_obj.id) ? Number(room.owner_obj.id) : (room.owner || room.owner_id ? Number(room.owner || room.owner_id) : null);
              if(uid && ownerIdForCompare && uid !== ownerIdForCompare){
                const dem = document.createElement('button'); dem.className='btn'; dem.textContent='Demote'; dem.addEventListener('click', async ()=>{ try{ dem.disabled = true; const res = await fetch('/rooms/' + room.id + '/admins/remove', { method:'POST', credentials:'include', headers: Object.assign({'Content-Type':'application/json'}, authHeaders('application/json')), body: JSON.stringify({ user_id: uid }) }); if(res && res.status === 200){ showToast && showToast('Demoted','success'); await refreshLists(); } else { const b = await res.json().catch(()=>null); showToast && showToast('Failed: '+JSON.stringify(b),'error'); } }catch(e){ console.warn(e); showToast && showToast('Failed','error'); } finally{ dem.disabled = false; } }); actions.appendChild(dem);
              }
            });

            // members: promote, ban, kick
            Array.from(membersList.querySelectorAll('li')).forEach(li=>{
              const u = li._user; let actions = li.querySelector('span:last-child');
              if(!actions){ actions = document.createElement('span'); actions.style.display='inline-flex'; actions.style.gap='6px'; li.appendChild(actions); }
              actions.innerHTML = '';
              if(!u) return;
              const rawId = (typeof u.id !== 'undefined' ? u.id : (typeof u.user_id !== 'undefined' ? u.user_id : u.name));
              const uid = (typeof rawId !== 'undefined' && rawId !== null && rawId !== '') ? Number(rawId) : null;
              if(!uid) return;
              // Promote to admin
              const promote = document.createElement('button'); promote.className='btn'; promote.textContent='Promote'; promote.addEventListener('click', async ()=>{ try{ promote.disabled = true; const res = await fetch('/rooms/' + room.id + '/admins/add', { method:'POST', credentials:'include', headers: Object.assign({'Content-Type':'application/json'}, authHeaders('application/json')), body: JSON.stringify({ user_id: uid }) }); if(res && res.status === 200){ showToast && showToast('Promoted','success'); await refreshLists(); } else { const b = await res.json().catch(()=>null); showToast && showToast('Failed: '+JSON.stringify(b),'error'); } }catch(e){ console.warn(e); showToast && showToast('Failed','error'); } finally{ promote.disabled = false; } }); actions.appendChild(promote);
              // Ban
              const ban = document.createElement('button'); ban.className='btn'; ban.textContent='Ban'; ban.addEventListener('click', async ()=>{ try{ ban.disabled = true; const res = await fetch('/rooms/' + room.id + '/ban', { method:'POST', credentials:'include', headers: Object.assign({'Content-Type':'application/json'}, authHeaders('application/json')), body: JSON.stringify({ user_id: uid }) }); if(res && res.status === 200){ showToast && showToast('Banned','success'); await refreshLists(); } else { const b = await res.json().catch(()=>null); showToast && showToast('Failed: '+JSON.stringify(b),'error'); } }catch(e){ console.warn(e); showToast && showToast('Failed','error'); } finally{ ban.disabled = false; } }); actions.appendChild(ban);
              // Remove (ban) — removing a member is treated as a permanent ban: the user cannot rejoin unless unbanned
              const kick = document.createElement('button'); kick.className='btn'; kick.textContent='Remove (ban)'; kick.title='Removing a member is treated as a ban — they will not be able to rejoin unless unbanned.'; kick.addEventListener('click', async ()=>{
                const userName = u.display_name || u.name || u.username || String(uid);
                const confirmed = window.confirm('Remove "' + userName + '" from this room?\n\nNote: Removing a member is treated as a permanent ban. They will lose access to the room, its messages, and files, and cannot rejoin unless an admin unbans them.');
                if(!confirmed) return;
                try{ kick.disabled = true; const res = await fetch('/rooms/' + room.id + '/members/remove', { method:'POST', credentials:'include', headers: Object.assign({'Content-Type':'application/json'}, authHeaders('application/json')), body: JSON.stringify({ user_id: uid }) }); if(res && res.status === 200){ showToast && showToast('User removed and banned','success'); await refreshLists(); } else { const b = await res.json().catch(()=>null); showToast && showToast('Failed: '+JSON.stringify(b),'error'); } }catch(e){ console.warn(e); showToast && showToast('Failed','error'); } finally{ try{ kick.disabled = false; }catch(e){} } }); actions.appendChild(kick);
            });
          }

          wireActions();
          await refreshLists();

          // ── Ban a user by username ──────────────────────────────────────────
          const banUserSection = document.createElement('div');
          banUserSection.style.cssText = 'border-top:1px solid #e8ecf0;padding-top:12px;margin-top:4px;';
          const buH = document.createElement('h4'); buH.textContent = 'Ban a user'; buH.style.marginBottom = '8px'; banUserSection.appendChild(buH);

          const banForm = document.createElement('div'); banForm.style.cssText = 'display:flex;gap:8px;align-items:flex-start;flex-wrap:wrap;position:relative;';
          const banInput = document.createElement('input');
          banInput.type = 'text'; banInput.placeholder = 'Search by username…';
          banInput.style.cssText = 'flex:1;min-width:160px;padding:6px 10px;border:1px solid #cdd4dc;border-radius:6px;font-size:0.95em;';
          banInput.setAttribute('autocomplete', 'off');

          const suggestionsBox = document.createElement('ul');
          suggestionsBox.style.cssText = 'position:absolute;top:100%;left:0;right:60px;background:#fff;border:1px solid #cdd4dc;border-radius:6px;margin:2px 0 0 0;padding:0;list-style:none;z-index:999;box-shadow:0 4px 16px rgba(0,0,0,.1);max-height:180px;overflow-y:auto;display:none;';

          let banTargetUser = null;
          let searchTimer = null;

          banInput.addEventListener('input', ()=>{
            clearTimeout(searchTimer);
            banTargetUser = null;
            banBtn.disabled = true;
            const q = banInput.value.trim();
            if(q.length < 2){ suggestionsBox.style.display = 'none'; suggestionsBox.innerHTML = ''; return; }
            searchTimer = setTimeout(async ()=>{
              try{
                const res = await fetch('/users/search?q=' + encodeURIComponent(q), { credentials: 'include', headers: authHeaders('application/json') });
                if(!res || res.status !== 200){ return; }
                const data = await res.json().catch(()=>null);
                const users = (data && data.users) || [];
                suggestionsBox.innerHTML = '';
                if(users.length === 0){
                  const li = document.createElement('li');
                  li.style.cssText = 'padding:8px 12px;color:var(--muted,#888);font-size:.9em;';
                  li.textContent = 'No users found';
                  suggestionsBox.appendChild(li);
                } else {
                  users.forEach(u=>{
                    const li = document.createElement('li');
                    li.style.cssText = 'padding:8px 12px;cursor:pointer;font-size:.95em;border-bottom:1px solid #f3f5f8;';
                    li.textContent = u.username || u.email || String(u.id);
                    li.addEventListener('mouseenter', ()=>{ li.style.background='#f3f7fb'; });
                    li.addEventListener('mouseleave', ()=>{ li.style.background=''; });
                    li.addEventListener('mousedown', (e)=>{
                      e.preventDefault();
                      banTargetUser = u;
                      banInput.value = u.username || u.email || String(u.id);
                      suggestionsBox.style.display = 'none';
                      banBtn.disabled = false;
                      banInput.focus();
                    });
                    suggestionsBox.appendChild(li);
                  });
                }
                suggestionsBox.style.display = 'block';
              }catch(e){ console.warn('user search failed', e); }
            }, 250);
          });

          banInput.addEventListener('blur', ()=>{ setTimeout(()=>{ suggestionsBox.style.display = 'none'; }, 150); });
          banInput.addEventListener('focus', ()=>{ if(suggestionsBox.children.length > 0) suggestionsBox.style.display = 'block'; });

          const banBtn = document.createElement('button');
          banBtn.className = 'btn'; banBtn.textContent = 'Ban'; banBtn.disabled = true;
          banBtn.style.cssText = 'background:#e74c3c;color:#fff;border:none;padding:6px 16px;border-radius:6px;cursor:pointer;font-weight:600;white-space:nowrap;';
          banBtn.addEventListener('click', async ()=>{
            if(!banTargetUser) return;
            const userName = banTargetUser.username || banTargetUser.email || String(banTargetUser.id);
            const confirmed = window.confirm('Ban "' + userName + '" from this room?\n\nThey will be removed and cannot rejoin unless an admin unbans them.');
            if(!confirmed) return;
            try{
              banBtn.disabled = true;
              const res = await fetch('/rooms/' + room.id + '/ban', { method:'POST', credentials:'include', headers: Object.assign({'Content-Type':'application/json'}, authHeaders('application/json')), body: JSON.stringify({ user_id: banTargetUser.id }) });
              if(res && res.status === 200){
                showToast && showToast('"' + userName + '" has been banned','success');
                banInput.value = ''; banTargetUser = null; banBtn.disabled = true;
                await refreshLists();
              } else {
                const b = await res.json().catch(()=>null);
                showToast && showToast('Failed: ' + (b && b.detail ? b.detail : JSON.stringify(b)), 'error');
                banBtn.disabled = false;
              }
            }catch(e){ console.warn('ban failed', e); showToast && showToast('Failed','error'); banBtn.disabled = false; }
          });

          const inputWrap = document.createElement('div'); inputWrap.style.cssText = 'position:relative;flex:1;min-width:160px;';
          inputWrap.appendChild(banInput); inputWrap.appendChild(suggestionsBox);
          banForm.appendChild(inputWrap); banForm.appendChild(banBtn);
          banUserSection.appendChild(banForm);
          body.appendChild(banUserSection);
          // ── end Ban a user ──────────────────────────────────────────────────

          // ── Invite a user (private rooms only) ─────────────────────────────
          if(room.visibility === 'private'){
            const inviteSection = document.createElement('div');
            inviteSection.style.cssText = 'border-top:1px solid #e8ecf0;padding-top:12px;margin-top:4px;';
            const invH = document.createElement('h4'); invH.textContent = 'Invite a user'; invH.style.marginBottom = '8px'; inviteSection.appendChild(invH);

            const invForm = document.createElement('div'); invForm.style.cssText = 'display:flex;gap:8px;align-items:flex-start;flex-wrap:wrap;position:relative;';
            const invInput = document.createElement('input');
            invInput.type = 'text'; invInput.placeholder = 'Search by username…';
            invInput.style.cssText = 'flex:1;min-width:160px;padding:6px 10px;border:1px solid #cdd4dc;border-radius:6px;font-size:0.95em;';
            invInput.setAttribute('autocomplete', 'off');

            const invSuggestions = document.createElement('ul');
            invSuggestions.style.cssText = 'position:absolute;top:100%;left:0;right:80px;background:#fff;border:1px solid #cdd4dc;border-radius:6px;margin:2px 0 0 0;padding:0;list-style:none;z-index:999;box-shadow:0 4px 16px rgba(0,0,0,.1);max-height:180px;overflow-y:auto;display:none;';

            let invTargetUser = null;
            let invSearchTimer = null;

            invInput.addEventListener('input', ()=>{
              clearTimeout(invSearchTimer);
              invTargetUser = null;
              inviteBtn.disabled = true;
              const q = invInput.value.trim();
              if(q.length < 2){ invSuggestions.style.display = 'none'; invSuggestions.innerHTML = ''; return; }
              invSearchTimer = setTimeout(async ()=>{
                try{
                  const res = await fetch('/users/search?q=' + encodeURIComponent(q), { credentials: 'include', headers: authHeaders('application/json') });
                  if(!res || res.status !== 200){ return; }
                  const data = await res.json().catch(()=>null);
                  const users = (data && data.users) || [];
                  invSuggestions.innerHTML = '';
                  if(users.length === 0){
                    const li = document.createElement('li');
                    li.style.cssText = 'padding:8px 12px;color:var(--muted,#888);font-size:.9em;';
                    li.textContent = 'No users found';
                    invSuggestions.appendChild(li);
                  } else {
                    users.forEach(u=>{
                      const li = document.createElement('li');
                      li.style.cssText = 'padding:8px 12px;cursor:pointer;font-size:.95em;border-bottom:1px solid #f3f5f8;';
                      li.textContent = u.username || u.email || String(u.id);
                      li.addEventListener('mouseenter', ()=>{ li.style.background='#f3f7fb'; });
                      li.addEventListener('mouseleave', ()=>{ li.style.background=''; });
                      li.addEventListener('mousedown', (e)=>{
                        e.preventDefault();
                        invTargetUser = u;
                        invInput.value = u.username || u.email || String(u.id);
                        invSuggestions.style.display = 'none';
                        inviteBtn.disabled = false;
                        invInput.focus();
                      });
                      invSuggestions.appendChild(li);
                    });
                  }
                  invSuggestions.style.display = 'block';
                }catch(e){ console.warn('invite user search failed', e); }
              }, 250);
            });

            invInput.addEventListener('blur', ()=>{ setTimeout(()=>{ invSuggestions.style.display = 'none'; }, 150); });
            invInput.addEventListener('focus', ()=>{ if(invSuggestions.children.length > 0) invSuggestions.style.display = 'block'; });

            const inviteBtn = document.createElement('button');
            inviteBtn.className = 'btn'; inviteBtn.textContent = 'Invite'; inviteBtn.disabled = true;
            inviteBtn.style.cssText = 'background:#2563eb;color:#fff;border:none;padding:6px 16px;border-radius:6px;cursor:pointer;font-weight:600;white-space:nowrap;';
            inviteBtn.addEventListener('click', async ()=>{
              if(!invTargetUser) return;
              try{
                inviteBtn.disabled = true;
                const res = await fetch('/rooms/' + room.id + '/invite', {
                  method: 'POST', credentials: 'include',
                  headers: Object.assign({'Content-Type':'application/json'}, authHeaders('application/json')),
                  body: JSON.stringify({ invitee_id: invTargetUser.id })
                });
                if(res && res.status === 200){
                  const userName = invTargetUser.username || invTargetUser.email || String(invTargetUser.id);
                  showToast && showToast('"' + userName + '" has been invited', 'success');
                  invInput.value = ''; invTargetUser = null; inviteBtn.disabled = true;
                } else {
                  const b = await res.json().catch(()=>null);
                  showToast && showToast('Failed: ' + (b && b.detail ? b.detail : JSON.stringify(b)), 'error');
                  inviteBtn.disabled = false;
                }
              }catch(e){ console.warn('invite failed', e); showToast && showToast('Failed', 'error'); inviteBtn.disabled = false; }
            });

            const invInputWrap = document.createElement('div'); invInputWrap.style.cssText = 'position:relative;flex:1;min-width:160px;';
            invInputWrap.appendChild(invInput); invInputWrap.appendChild(invSuggestions);
            invForm.appendChild(invInputWrap); invForm.appendChild(inviteBtn);
            inviteSection.appendChild(invForm);
            body.appendChild(inviteSection);
          }
          // ── end Invite a user ───────────────────────────────────────────────

          await window.showModal({ title: 'Manage room ' + (room.name || room.id), body: body, html: true, confirmText: 'Close' });
        }catch(e){ console.warn('manage clicked', e); }
      });

      btnGoToChat.addEventListener('click', ()=>{ try{ const rid = room && room.id; if(!rid) return; location.href = '/static/chat/index.html?room=' + encodeURIComponent(rid); }catch(e){} });

  try{ const panelEl = document.getElementById('room-details'); if(panelEl) panelEl.style.display = 'none'; }catch(e){}
  await window.showModal({ title: 'Room details ' + (room.name ? ('- ' + room.name) : ''), body: container, html: true, confirmText: 'Close' });
      return;
    }catch(e){ console.warn('renderRoomDetails modal failed', e); }
  }

  // populate fields into the inline details panel as a fallback when modal is not available
  const nameEl = document.getElementById('room-name'); const descEl = document.getElementById('room-description');
  const visEl = document.getElementById('room-visibility'); const ownerEl = document.getElementById('room-owner');
  const adminsEl = document.getElementById('room-admins'); const membersEl = document.getElementById('room-members'); const bannedEl = document.getElementById('room-banned');
  const btnJoin = document.getElementById('btn-join-room'); const btnLeave = document.getElementById('btn-leave-room'); const btnManage = document.getElementById('btn-manage-room');
  const btnDelete = (document.getElementById && document.getElementById('btn-delete-room')) || null;
  const btnGoToChat = (document.getElementById && document.getElementById('btn-go-to-chat')) || null;
      // optional debug logging — enable in browser via `window.ROOMS_DEBUG = true`
      try{
        if(typeof window !== 'undefined' && window.ROOMS_DEBUG){
          try{ console.debug('renderRoomDetails: room=', room); }catch(e){}
          try{ console.debug('btnJoin exists=', !!btnJoin, 'btnLeave exists=', !!btnLeave, 'btnManage exists=', !!btnManage, 'btnDelete exists=', !!btnDelete); }catch(e){}
          try{ if(btnJoin) console.debug('btnJoin computed display=', window.getComputedStyle(btnJoin).display); }catch(e){}
          try{ if(btnManage) console.debug('btnManage computed display=', window.getComputedStyle(btnManage).display); }catch(e){}
          try{ if(btnDelete) console.debug('btnDelete computed display=', window.getComputedStyle(btnDelete).display); }catch(e){}
        }
      }catch(e){}
      nameEl.textContent = room.name || ('room' + room.id);
  descEl.textContent = room.description || '—';
      visEl.textContent = (room.visibility || 'public');
    // Prefer richer owner object `owner_obj` when available, otherwise fall back to legacy `owner` or `owner_id`.
  const ownerObj = room.owner_obj || (room.owner && typeof room.owner === 'object' ? room.owner : null);
  const ownerId = (room.owner && typeof room.owner !== 'object') ? room.owner : room.owner_id;
  ownerEl.textContent = (ownerObj && (ownerObj.display_name || ownerObj.name || ownerObj.username)) || (ownerId ? String(ownerId) : '—');

      // populate admins/members/banned lists
  function listPopulate(container, items){ if(!container) return; container.innerHTML = ''; if(!items || items.length === 0){ const li = document.createElement('li'); li.style.color='var(--muted)'; li.textContent = '—'; container.appendChild(li); return; } items.forEach(u=>{ const li = document.createElement('li'); let label = ''; try{ if(u && (u.display_name || u.name)) label = u.display_name || u.name; else if(u && u.username) label = u.username; else if(typeof u === 'number' || (u && typeof u.id !== 'undefined')) label = (u && (u.username || u.id)) || String(u); else label = String(u); }catch(e){ label = String(u); } li.textContent = label; container.appendChild(li); }); }
  // prefer rich info objects if available (owner_obj, admins_info, members_info, bans_info)
  // prefer rich info arrays when available, otherwise fall back to id arrays
  listPopulate(adminsEl, room.admins_info || (room.admins || []).map(id=>({ id })));
  listPopulate(membersEl, room.members_info || (room.members || []).map(id=>({ id })));
  // server returns `bans` list of ids and `bans_info` richer objects
  const bansList = room.bans_info || (room.bans || room.banned || []).map(id=>({ id }));
  listPopulate(bannedEl, bansList);
  try{ const bannedCountEl = document.getElementById('room-banned-count'); if(bannedCountEl){ bannedCountEl.textContent = String(bansList.length || 0); } }catch(e){}

      // show/hide buttons based on membership/role
      try{ if(room.is_member){ btnJoin.style.display = 'none'; btnLeave.style.display = 'inline-flex'; } else { btnJoin.style.display = 'inline-flex'; btnLeave.style.display = 'none'; } }catch(e){}
  try{ if(room.is_owner || room.is_admin){ btnManage.style.display = 'inline-flex'; if(btnDelete) btnDelete.style.display = 'inline-flex'; } else { btnManage.style.display = 'none'; if(btnDelete) btnDelete.style.display = 'none'; } }catch(e){}
  try{ if(btnGoToChat) btnGoToChat.style.display = 'inline-flex'; }catch(e){}

      // If the current user is banned, hide all action buttons and show a ban notice
      try{
        const isCurrentUserBanned = room.is_banned === true;
        if(isCurrentUserBanned){
          try{ btnJoin.style.display = 'none'; }catch(e){}
          try{ btnLeave.style.display = 'none'; }catch(e){}
          try{ if(btnGoToChat) btnGoToChat.style.display = 'none'; }catch(e){}
          try{ if(btnManage) btnManage.style.display = 'none'; }catch(e){}
          try{ if(btnDelete) btnDelete.style.display = 'none'; }catch(e){}
          const panel = document.getElementById('room-details');
          if(panel && !panel.querySelector('.ban-notice')){
            const banNotice = document.createElement('div');
            banNotice.className = 'ban-notice';
            banNotice.style.cssText = 'background:#fdecea;border:1px solid #e57373;border-radius:6px;color:#c0392b;font-weight:600;padding:10px 14px;margin:8px 0;display:flex;align-items:center;gap:8px;';
            const bannedByName = room.banned_by && (room.banned_by.username || room.banned_by.email);
            const bannedByText = bannedByName ? ` Banned by: ${bannedByName}.` : '';
            banNotice.innerHTML = `<span style="font-size:1.2em;">🚫</span><span>You have been banned from this room and cannot rejoin. Contact an admin to appeal.${bannedByText}</span>`;
            const actionsRow = panel.querySelector('.room-actions') || panel;
            actionsRow.insertBefore(banNotice, actionsRow.firstChild);
          }
        }
      }catch(e){}

      // delete button: only visible to owner or admin; wire click handler
      try{
        if(btnDelete){
          btnDelete.onclick = async ()=>{
            try{
              btnDelete.disabled = true;
              // ensure shared UI exists
              try{ if(window && typeof window.showModal !== 'function'){ const s = document.createElement('script'); s.async = true; s.src = '/static/app/ui/ui.js?_=' + Date.now(); document.head.appendChild(s); } }catch(e){}
              const opts = { title: 'Delete room', body: (room.name ? `Delete room "${room.name}"? This cannot be undone.` : 'Delete this room? This cannot be undone.'), confirmText: 'Delete', cancelText: 'Cancel' };
              let ok = false;
              try{
                if(window && typeof window.showModal === 'function') ok = await window.showModal(opts);
                else ok = window.confirm(opts.body);
              }catch(e){ ok = false; }
              if(!ok) return;
              // perform DELETE
              const d = await fetch('/rooms/' + room.id, { method: 'DELETE', credentials: 'include', headers: authHeaders('application/json') });
              if(d && (d.status === 200 || d.status === 204)){
                showToast && showToast('Room deleted','success');
                // remove the room from the list UI and hide details
                try{ const li = document.querySelector('#rooms-list li[data-id="' + room.id + '"]'); if(li && li.parentElement) li.parentElement.removeChild(li); }catch(e){}
                try{ const panel = document.getElementById('room-details'); if(panel) panel.style.display = 'none'; }catch(e){}
                // refresh rooms list
                try{ renderRooms(); }catch(e){}
              } else {
                const body = await d.json().catch(()=>null);
                showToast && showToast('Failed to delete: ' + JSON.stringify(body),'error');
              }
            }catch(e){ console.warn('delete failed', e); showToast && showToast('Delete failed','error'); }
            finally{ try{ btnDelete.disabled = false; }catch(e){} }
          };
        }
      }catch(e){}

      // attach handlers (remove prior handlers by replacing with new functions)
      if(btnJoin){ btnJoin.onclick = async ()=>{
        try{ btnJoin.disabled = true; const id = room.id; showStatus && showStatus('Joining…'); const j = await fetch('/rooms/' + id + '/join', { method:'POST', credentials:'include', headers: authHeaders('application/json') }); if(j.status === 200){ showToast && showToast('Joined room','success'); renderRooms(); renderRoomDetails(Object.assign({}, room, { is_member: true })); } else { const body = await j.json().catch(()=>null); showToast && showToast('Failed to join: ' + JSON.stringify(body),'error'); } }catch(e){ console.warn('join failed', e); showToast && showToast('Join failed','error'); } finally{ btnJoin.disabled = false; } } }

      if(btnLeave){ btnLeave.onclick = async ()=>{
        try{ btnLeave.disabled = true; const id = room.id; showStatus && showStatus('Leaving…'); const l = await fetch('/rooms/' + id + '/leave', { method:'POST', credentials:'include', headers: authHeaders('application/json') }); if(l.status === 200){ showToast && showToast('Left room','success'); renderRooms(); renderRoomDetails(Object.assign({}, room, { is_member: false })); } else { const body = await l.json().catch(()=>null); showToast && showToast('Failed to leave: ' + JSON.stringify(body),'error'); } }catch(e){ console.warn('leave failed', e); showToast && showToast('Leave failed','error'); } finally{ btnLeave.disabled = false; } } }

      if(btnManage){ btnManage.onclick = async ()=>{
        try{
          // Build a manage UI fragment (admins, members, banned) and show in modal
          // normalize items into objects { id, display_name }
          const makeList = (items, emptyText='—')=>{
            const ul = document.createElement('ul'); ul.style.listStyle='none'; ul.style.padding='0'; ul.style.margin='0'; ul.style.display='grid'; ul.style.gap='6px';
            if(!items || items.length === 0){ const li = document.createElement('li'); li.style.color='var(--muted)'; li.textContent = emptyText; ul.appendChild(li); return ul; }
            items.forEach(item=>{
              const u = (item && typeof item === 'object') ? (item.id ? { id: item.id, display_name: item.display_name || item.username || item.name } : (item.name ? { id: Number(item.name), display_name: item.display_name || item.name } : { id: null, display_name: String(item) })) : { id: Number(item), display_name: String(item) };
              const li = document.createElement('li'); li.style.display='flex'; li.style.justifyContent='space-between'; li.style.alignItems='center';
              const name = document.createElement('span'); name.textContent = u.display_name || (u.id ? String(u.id) : '—');
              const actions = document.createElement('span'); actions.style.display='inline-flex'; actions.style.gap='6px';
              li.appendChild(name); li.appendChild(actions); li._user = u; ul.appendChild(li);
            });
            return ul;
          };

          const body = document.createElement('div');
          body.style.display='grid'; body.style.gap='12px';

          // Admins
          const adminsSection = document.createElement('div');
          const aH = document.createElement('h4'); aH.textContent = 'Admins'; adminsSection.appendChild(aH);
          const adminsList = makeList(room.admins_info || room.admins || []);
          adminsSection.appendChild(adminsList);
          body.appendChild(adminsSection);

          // Members
          const membersSection = document.createElement('div');
          const mH = document.createElement('h4'); mH.textContent = 'Members'; membersSection.appendChild(mH);
          const membersList = makeList(room.members_info || room.members || []);
          membersSection.appendChild(membersList);
          body.appendChild(membersSection);

          // Banned
          const bannedSection = document.createElement('div');
          const bH = document.createElement('h4'); bH.textContent = 'Banned users'; bannedSection.appendChild(bH);
          const bannedList = makeList(room.bans_info || room.bans || room.banned || []);
          bannedSection.appendChild(bannedList);
          body.appendChild(bannedSection);

          // helper: refresh lists from server
          async function refreshLists(){
            try{
              const dr = await fetch('/rooms/' + room.id, { credentials: 'include', headers: authHeaders('application/json') });
              if(dr && dr.status === 200){ const data = await dr.json().catch(()=>null); const fresh = (data && data.room) ? data.room : null; if(fresh){
                // update lists (prefer richer info if present)
                const admins = fresh.admins_info || fresh.admins || [];
                const members = fresh.members_info || fresh.members || [];
                const bans = fresh.bans_info || fresh.bans || fresh.banned || [];
                // rebuild adminsList
                const newAdmins = makeList(admins, 'No admins'); adminsSection.replaceChild(newAdmins, adminsList);
                // rebuild members
                const newMembers = makeList(members, 'No members'); membersSection.replaceChild(newMembers, membersList);
                // rebuild bans
                const newBans = makeList(bans, 'No banned users'); bannedSection.replaceChild(newBans, bannedList);
              } }
            }catch(e){ console.warn('refreshLists failed', e); }
          }

          // attach action buttons to list items
          function wireActions(){
            Array.from(adminsList.querySelectorAll('li')).forEach(li=>{
              const u = li._user; let actions = li.querySelector('span:last-child');
              if(!actions){ actions = document.createElement('span'); actions.style.display='inline-flex'; actions.style.gap='6px'; li.appendChild(actions); }
              actions.innerHTML = '';
              const uid = Number(u.id);
              // show 'Demote' for admins except owner
              const ownerIdForCompare = (room.owner_obj && room.owner_obj.id) ? Number(room.owner_obj.id) : (room.owner || room.owner_id ? Number(room.owner || room.owner_id) : null);
              if(uid && ownerIdForCompare && uid !== ownerIdForCompare){
                const dem = document.createElement('button'); dem.className='btn'; dem.textContent='Demote'; dem.addEventListener('click', async ()=>{
                  try{ dem.disabled = true; const res = await fetch('/rooms/' + room.id + '/admins/remove', { method:'POST', credentials:'include', headers: Object.assign({'Content-Type':'application/json'}, authHeaders('application/json')), body: JSON.stringify({ user_id: uid }) }); if(res && res.status === 200){ showToast && showToast('Demoted','success'); await refreshLists(); } else { const b = await res.json().catch(()=>null); showToast && showToast('Failed: '+JSON.stringify(b),'error'); } }catch(e){ console.warn(e); showToast && showToast('Failed','error'); } finally{ dem.disabled = false; } }); actions.appendChild(dem); }
            });

            Array.from(membersList.querySelectorAll('li')).forEach(li=>{
              const u = li._user; let actions = li.querySelector('span:last-child');
              if(!actions){ actions = document.createElement('span'); actions.style.display='inline-flex'; actions.style.gap='6px'; li.appendChild(actions); }
              actions.innerHTML = '';
              if(!u) return;
              const rawId = (typeof u.id !== 'undefined' ? u.id : (typeof u.user_id !== 'undefined' ? u.user_id : u.name));
              const uid = (typeof rawId !== 'undefined' && rawId !== null && rawId !== '') ? Number(rawId) : null;
              if(!uid) return;
              // Promote button
              const promote = document.createElement('button'); promote.className='btn'; promote.textContent='Promote'; promote.addEventListener('click', async ()=>{
                try{ promote.disabled = true; const res = await fetch('/rooms/' + room.id + '/admins/add', { method:'POST', credentials:'include', headers: Object.assign({'Content-Type':'application/json'}, authHeaders('application/json')), body: JSON.stringify({ user_id: uid }) }); if(res && res.status === 200){ showToast && showToast('Promoted','success'); await refreshLists(); } else { const b = await res.json().catch(()=>null); showToast && showToast('Failed: '+JSON.stringify(b),'error'); } }catch(e){ console.warn(e); showToast && showToast('Failed','error'); } finally{ promote.disabled = false; } }); actions.appendChild(promote);
              // Ban button (explicit ban without removing from members list)
              const ban = document.createElement('button'); ban.className='btn'; ban.textContent='Ban'; ban.addEventListener('click', async ()=>{
                try{ ban.disabled = true; const res = await fetch('/rooms/' + room.id + '/ban', { method:'POST', credentials:'include', headers: Object.assign({'Content-Type':'application/json'}, authHeaders('application/json')), body: JSON.stringify({ user_id: uid }) }); if(res && res.status === 200){ showToast && showToast('Banned','success'); await refreshLists(); } else { const b = await res.json().catch(()=>null); showToast && showToast('Failed: '+JSON.stringify(b),'error'); } }catch(e){ console.warn(e); showToast && showToast('Failed','error'); } finally{ ban.disabled = false; } }); actions.appendChild(ban);
              // Remove (ban) — removing a member is treated as a permanent ban: the user cannot rejoin unless unbanned
              const kick = document.createElement('button'); kick.className='btn'; kick.textContent='Remove (ban)'; kick.title='Removing a member is treated as a ban — they will not be able to rejoin unless unbanned.'; kick.addEventListener('click', async ()=>{
                const userName = u.display_name || u.name || u.username || String(uid);
                const confirmed = window.confirm('Remove "' + userName + '" from this room?\n\nNote: Removing a member is treated as a permanent ban. They will lose access to the room, its messages, and files, and cannot rejoin unless an admin unbans them.');
                if(!confirmed) return;
                try{ kick.disabled = true; const res = await fetch('/rooms/' + room.id + '/members/remove', { method:'POST', credentials:'include', headers: Object.assign({'Content-Type':'application/json'}, authHeaders('application/json')), body: JSON.stringify({ user_id: uid }) }); if(res && res.status === 200){ showToast && showToast('User removed and banned','success'); await refreshLists(); } else { const b = await res.json().catch(()=>null); showToast && showToast('Failed: '+JSON.stringify(b),'error'); } }catch(e){ console.warn(e); showToast && showToast('Failed','error'); } finally{ try{ kick.disabled = false; }catch(e){} } }); actions.appendChild(kick);
            });

            Array.from(bannedList.querySelectorAll('li')).forEach(li=>{
              const u = li._user; let actions = li.querySelector('span:last-child');
              if(!actions){ actions = document.createElement('span'); actions.style.display='inline-flex'; actions.style.gap='6px'; li.appendChild(actions); }
              actions.innerHTML = '';
              if(!u) return;
              const rawId = (typeof u.id !== 'undefined' ? u.id : (typeof u.user_id !== 'undefined' ? u.user_id : u.name));
              const uid = (typeof rawId !== 'undefined' && rawId !== null && rawId !== '') ? Number(rawId) : null;
              if(!uid) return;
              const unban = document.createElement('button'); unban.className='btn'; unban.textContent='Unban'; unban.addEventListener('click', async ()=>{
                try{ unban.disabled = true; const res = await fetch('/rooms/' + room.id + '/unban', { method:'POST', credentials:'include', headers: Object.assign({'Content-Type':'application/json'}, authHeaders('application/json')), body: JSON.stringify({ user_id: uid }) }); if(res && res.status === 200){ showToast && showToast('Unbanned','success'); await refreshLists(); } else { const b = await res.json().catch(()=>null); showToast && showToast('Failed: '+JSON.stringify(b),'error'); } }catch(e){ console.warn(e); showToast && showToast('Failed','error'); } finally{ unban.disabled = false; } }); actions.appendChild(unban);
            });
          }

          // initialize wiring before showing modal
          wireActions();

          // ── Ban a user by username ──────────────────────────────────────────
          const banUserSection2 = document.createElement('div');
          banUserSection2.style.cssText = 'border-top:1px solid #e8ecf0;padding-top:12px;margin-top:4px;';
          const buH2 = document.createElement('h4'); buH2.textContent = 'Ban a user'; buH2.style.marginBottom = '8px'; banUserSection2.appendChild(buH2);

          const banForm2 = document.createElement('div'); banForm2.style.cssText = 'display:flex;gap:8px;align-items:flex-start;flex-wrap:wrap;position:relative;';
          const banInput2 = document.createElement('input');
          banInput2.type = 'text'; banInput2.placeholder = 'Search by username…';
          banInput2.style.cssText = 'flex:1;min-width:160px;padding:6px 10px;border:1px solid #cdd4dc;border-radius:6px;font-size:0.95em;';
          banInput2.setAttribute('autocomplete', 'off');

          const suggestionsBox2 = document.createElement('ul');
          suggestionsBox2.style.cssText = 'position:absolute;top:100%;left:0;right:60px;background:#fff;border:1px solid #cdd4dc;border-radius:6px;margin:2px 0 0 0;padding:0;list-style:none;z-index:999;box-shadow:0 4px 16px rgba(0,0,0,.1);max-height:180px;overflow-y:auto;display:none;';

          let banTargetUser2 = null;
          let searchTimer2 = null;

          banInput2.addEventListener('input', ()=>{
            clearTimeout(searchTimer2);
            banTargetUser2 = null;
            banBtn2.disabled = true;
            const q = banInput2.value.trim();
            if(q.length < 2){ suggestionsBox2.style.display = 'none'; suggestionsBox2.innerHTML = ''; return; }
            searchTimer2 = setTimeout(async ()=>{
              try{
                const res = await fetch('/users/search?q=' + encodeURIComponent(q), { credentials: 'include', headers: authHeaders('application/json') });
                if(!res || res.status !== 200){ return; }
                const data = await res.json().catch(()=>null);
                const users = (data && data.users) || [];
                suggestionsBox2.innerHTML = '';
                if(users.length === 0){
                  const li = document.createElement('li');
                  li.style.cssText = 'padding:8px 12px;color:var(--muted,#888);font-size:.9em;';
                  li.textContent = 'No users found';
                  suggestionsBox2.appendChild(li);
                } else {
                  users.forEach(u=>{
                    const li = document.createElement('li');
                    li.style.cssText = 'padding:8px 12px;cursor:pointer;font-size:.95em;border-bottom:1px solid #f3f5f8;';
                    li.textContent = u.username || u.email || String(u.id);
                    li.addEventListener('mouseenter', ()=>{ li.style.background='#f3f7fb'; });
                    li.addEventListener('mouseleave', ()=>{ li.style.background=''; });
                    li.addEventListener('mousedown', (e)=>{
                      e.preventDefault();
                      banTargetUser2 = u;
                      banInput2.value = u.username || u.email || String(u.id);
                      suggestionsBox2.style.display = 'none';
                      banBtn2.disabled = false;
                      banInput2.focus();
                    });
                    suggestionsBox2.appendChild(li);
                  });
                }
                suggestionsBox2.style.display = 'block';
              }catch(e){ console.warn('user search failed', e); }
            }, 250);
          });

          banInput2.addEventListener('blur', ()=>{ setTimeout(()=>{ suggestionsBox2.style.display = 'none'; }, 150); });
          banInput2.addEventListener('focus', ()=>{ if(suggestionsBox2.children.length > 0) suggestionsBox2.style.display = 'block'; });

          const banBtn2 = document.createElement('button');
          banBtn2.className = 'btn'; banBtn2.textContent = 'Ban'; banBtn2.disabled = true;
          banBtn2.style.cssText = 'background:#e74c3c;color:#fff;border:none;padding:6px 16px;border-radius:6px;cursor:pointer;font-weight:600;white-space:nowrap;';
          banBtn2.addEventListener('click', async ()=>{
            if(!banTargetUser2) return;
            const userName2 = banTargetUser2.username || banTargetUser2.email || String(banTargetUser2.id);
            const confirmed = window.confirm('Ban "' + userName2 + '" from this room?\n\nThey will be removed and cannot rejoin unless an admin unbans them.');
            if(!confirmed) return;
            try{
              banBtn2.disabled = true;
              const res = await fetch('/rooms/' + room.id + '/ban', { method:'POST', credentials:'include', headers: Object.assign({'Content-Type':'application/json'}, authHeaders('application/json')), body: JSON.stringify({ user_id: banTargetUser2.id }) });
              if(res && res.status === 200){
                showToast && showToast('"' + userName2 + '" has been banned','success');
                banInput2.value = ''; banTargetUser2 = null; banBtn2.disabled = true;
                await refreshLists();
              } else {
                const b = await res.json().catch(()=>null);
                showToast && showToast('Failed: ' + (b && b.detail ? b.detail : JSON.stringify(b)), 'error');
                banBtn2.disabled = false;
              }
            }catch(e){ console.warn('ban failed', e); showToast && showToast('Failed','error'); banBtn2.disabled = false; }
          });

          const inputWrap2 = document.createElement('div'); inputWrap2.style.cssText = 'position:relative;flex:1;min-width:160px;';
          inputWrap2.appendChild(banInput2); inputWrap2.appendChild(suggestionsBox2);
          banForm2.appendChild(inputWrap2); banForm2.appendChild(banBtn2);
          banUserSection2.appendChild(banForm2);
          body.appendChild(banUserSection2);
          // ── end Ban a user ──────────────────────────────────────────────────

          if(window && typeof window.showModal === 'function'){
            await window.showModal({ title: 'Manage room ' + (room.name || room.id), body: body, html: true, confirmText: 'Close' });
          } else {
            // Try to load the shared UI script and use the modal if it becomes available
            try{
              if(window && typeof window.showModal !== 'function'){
                await new Promise((resolve)=>{
                  try{
                    const s = document.createElement('script');
                    s.async = true;
                    s.src = '/static/app/ui/ui.js?_=' + Date.now();
                    s.onload = ()=>{ setTimeout(()=>resolve(), 0); };
                    s.onerror = ()=>{ resolve(); };
                    document.head.appendChild(s);
                  }catch(e){ resolve(); }
                });
              }
            }catch(e){}

            if(window && typeof window.showModal === 'function'){
              await window.showModal({ title: 'Manage room ' + (room.name || room.id), body: body, html: true, confirmText: 'Close' });
            } else {
              // final fallback: append to body
              document.body.appendChild(body);
            }
          }

        }catch(e){ console.warn('manage clicked', e); }
      } }

  if(btnGoToChat){ btnGoToChat.onclick = ()=>{ try{ const rid = room && room.id; if(!rid) return; location.href = '/static/chat/index.html?room=' + encodeURIComponent(rid); }catch(e){} }; }

      panel.style.display = 'block';
    }catch(e){ console.warn('renderRoomDetails failed', e); }
  }

  try{ window.selectRoom = window.selectRoom || function(r){ try{ renderRoomDetails(r); }catch(e){} }; }catch(e){}

  try{ window.roomsApi = window.roomsApi || {}; window.roomsApi.renderRooms = renderRooms; window.roomsApi.renderRoomDetails = renderRoomDetails; }catch(e){}
})();
