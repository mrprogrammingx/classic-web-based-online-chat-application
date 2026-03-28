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
            // Only intercept clicks when we're already on the chat page (so we intend in-page selection),
            // or on the rooms index (so we want to show details inline), or when a real messages container exists.
            const onChatPath = (typeof location !== 'undefined' && location.pathname && String(location.pathname).indexOf('/static/chat') !== -1);
            const onRoomsPath = (typeof location !== 'undefined' && location.pathname && String(location.pathname).indexOf('/static/rooms') !== -1);
            const messagesEl = document.querySelector && document.querySelector('#messages');
            const hasMessages = !!(messagesEl && messagesEl.parentElement);
            if(window && typeof window.selectRoom === 'function' && (onChatPath || onRoomsPath || hasMessages)){
              ev.preventDefault();
              try{ window.selectRoom(r); }catch(e){}
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
          if(r && r.is_member){
            joinBtn.style.display = 'none';
            leaveBtn.style.display = 'inline-flex';
          } else {
            joinBtn.style.display = 'inline-flex';
            leaveBtn.style.display = 'none';
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

      // populate fields
      const nameEl = document.getElementById('room-name'); const descEl = document.getElementById('room-description');
      const visEl = document.getElementById('room-visibility'); const ownerEl = document.getElementById('room-owner');
      const adminsEl = document.getElementById('room-admins'); const membersEl = document.getElementById('room-members'); const bannedEl = document.getElementById('room-banned');
      const btnJoin = document.getElementById('btn-join-room'); const btnLeave = document.getElementById('btn-leave-room'); const btnManage = document.getElementById('btn-manage-room');
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
      try{ if(room.is_owner || room.is_admin){ btnManage.style.display = 'inline-flex'; } else { btnManage.style.display = 'none'; } }catch(e){}

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
          const adminsList = makeList(room.admins_info || room.admins || [], 'No admins');
          adminsSection.appendChild(adminsList);
          body.appendChild(adminsSection);

          // Members
          const membersSection = document.createElement('div');
          const mH = document.createElement('h4'); mH.textContent = 'Members'; membersSection.appendChild(mH);
          const membersList = makeList(room.members_info || room.members || [], 'No members');
          membersSection.appendChild(membersList);
          body.appendChild(membersSection);

          // Banned
          const bannedSection = document.createElement('div');
          const bH = document.createElement('h4'); bH.textContent = 'Banned users'; bannedSection.appendChild(bH);
          const bannedList = makeList(room.bans_info || room.bans || room.banned || [], 'No banned users');
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
              const u = li._user; const actions = li.querySelector('span:last-child'); actions.innerHTML = '';
              const uid = Number(u.id);
              // show 'Demote' for admins except owner
              const ownerIdForCompare = (room.owner_obj && room.owner_obj.id) ? Number(room.owner_obj.id) : (room.owner || room.owner_id ? Number(room.owner || room.owner_id) : null);
              if(uid && ownerIdForCompare && uid !== ownerIdForCompare){
                const dem = document.createElement('button'); dem.className='btn'; dem.textContent='Demote'; dem.addEventListener('click', async ()=>{
                  try{ dem.disabled = true; const res = await fetch('/rooms/' + room.id + '/admins/remove', { method:'POST', credentials:'include', headers: Object.assign({'Content-Type':'application/json'}, authHeaders('application/json')), body: JSON.stringify({ user_id: uid }) }); if(res && res.status === 200){ showToast && showToast('Demoted','success'); await refreshLists(); } else { const b = await res.json().catch(()=>null); showToast && showToast('Failed: '+JSON.stringify(b),'error'); } }catch(e){ console.warn(e); showToast && showToast('Failed','error'); } finally{ dem.disabled = false; } }); actions.appendChild(dem); }
            });

            Array.from(membersList.querySelectorAll('li')).forEach(li=>{
              const u = li._user; const actions = li.querySelector('span:last-child'); actions.innerHTML = '';
              const uid = Number(u.id);
              // Promote button
              const promote = document.createElement('button'); promote.className='btn'; promote.textContent='Promote'; promote.addEventListener('click', async ()=>{
                try{ promote.disabled = true; const res = await fetch('/rooms/' + room.id + '/admins/add', { method:'POST', credentials:'include', headers: Object.assign({'Content-Type':'application/json'}, authHeaders('application/json')), body: JSON.stringify({ user_id: uid }) }); if(res && res.status === 200){ showToast && showToast('Promoted','success'); await refreshLists(); } else { const b = await res.json().catch(()=>null); showToast && showToast('Failed: '+JSON.stringify(b),'error'); } }catch(e){ console.warn(e); showToast && showToast('Failed','error'); } finally{ promote.disabled = false; } }); actions.appendChild(promote);
              // Remove/Ban button
              const ban = document.createElement('button'); ban.className='btn'; ban.textContent='Ban'; ban.addEventListener('click', async ()=>{
                try{ ban.disabled = true; const res = await fetch('/rooms/' + room.id + '/ban', { method:'POST', credentials:'include', headers: Object.assign({'Content-Type':'application/json'}, authHeaders('application/json')), body: JSON.stringify({ user_id: uid }) }); if(res && res.status === 200){ showToast && showToast('Banned','success'); await refreshLists(); } else { const b = await res.json().catch(()=>null); showToast && showToast('Failed: '+JSON.stringify(b),'error'); } }catch(e){ console.warn(e); showToast && showToast('Failed','error'); } finally{ ban.disabled = false; } }); actions.appendChild(ban);
            });

            Array.from(bannedList.querySelectorAll('li')).forEach(li=>{
              const u = li._user; const actions = li.querySelector('span:last-child'); actions.innerHTML = '';
              const uid = Number(u.id);
              const unban = document.createElement('button'); unban.className='btn'; unban.textContent='Unban'; unban.addEventListener('click', async ()=>{
                try{ unban.disabled = true; const res = await fetch('/rooms/' + room.id + '/unban', { method:'POST', credentials:'include', headers: Object.assign({'Content-Type':'application/json'}, authHeaders('application/json')), body: JSON.stringify({ user_id: uid }) }); if(res && res.status === 200){ showToast && showToast('Unbanned','success'); await refreshLists(); } else { const b = await res.json().catch(()=>null); showToast && showToast('Failed: '+JSON.stringify(b),'error'); } }catch(e){ console.warn(e); showToast && showToast('Failed','error'); } finally{ unban.disabled = false; } }); actions.appendChild(unban);
            });
          }

          // initialize wiring before showing modal
          wireActions();

          if(window && typeof window.showModal === 'function'){
            await window.showModal({ title: 'Manage room ' + (room.name || room.id), body: body, html: true, confirmText: 'Close' });
          } else {
            // fallback: append to body
            document.body.appendChild(body);
          }

        }catch(e){ console.warn('manage clicked', e); }
      } }

      panel.style.display = 'block';
    }catch(e){ console.warn('renderRoomDetails failed', e); }
  }

  try{ window.selectRoom = window.selectRoom || function(r){ try{ renderRoomDetails(r); }catch(e){} }; }catch(e){}

  try{ window.roomsApi = window.roomsApi || {}; window.roomsApi.renderRooms = renderRooms; window.roomsApi.renderRoomDetails = renderRoomDetails; }catch(e){}
})();
