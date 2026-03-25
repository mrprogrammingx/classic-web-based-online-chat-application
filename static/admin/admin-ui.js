// Shared admin UI builder used by app.js and main.js
(function(){
  function escapeHtml(str){ return String(str||'').replace(/[&<>'"]/g,(s)=>({ '&':'&amp;','<':'&lt;','>':'&gt;',"'":"&#39;", '"':'&quot;' })[s]); }
  async function fetchJSON(url, opts){ try{ opts = opts || {}; if(typeof opts.credentials === 'undefined') opts.credentials = 'include'; opts.headers = opts.headers || {}; const r = await fetch(url, opts); if(!r.ok) return null; return await r.json().catch(()=>null); }catch(e){ console.warn('fetchJSON failed', e); return null } }
  function showToast(msg, type='error'){ try{ if(typeof window.showToast === 'function'){ window.showToast(msg, type); return; } }catch(e){} console.log('TOAST', type, msg); }
  function confirmModal(title, body){ // prefer a global showModal if available
    try{ if(typeof window.showModal === 'function') return window.showModal({title, body, confirmText: 'OK', cancelText: 'Cancel'}); }catch(e){}
    return Promise.resolve(confirm((title?title + '\n\n':'') + (body||'')) );
  }

  async function openAdminPanel(){
    // Fetch initial data in parallel
    const [users, rooms, banned] = await Promise.all([
      fetchJSON('/admin/users') || {},
      fetchJSON('/admin/rooms') || {},
      fetchJSON('/admin/banned') || {}
    ]);

    const root = document.getElementById('modal-root') || (function(){ const r=document.createElement('div'); r.id='modal-root'; document.body.appendChild(r); return r; })();
    root.innerHTML = '';
    const panel = document.createElement('div'); panel.className = 'admin-panel';
    const tabs = document.createElement('div'); tabs.className = 'tabs';
    const tabUsers = document.createElement('button'); tabUsers.textContent='Users'; tabUsers.className='active btn small';
    const tabBanned = document.createElement('button'); tabBanned.textContent='Banned'; tabBanned.className='btn small';
    const tabRooms = document.createElement('button'); tabRooms.textContent='Rooms'; tabRooms.className='btn small';
    tabs.appendChild(tabUsers); tabs.appendChild(tabBanned); tabs.appendChild(tabRooms);
    const body = document.createElement('div'); body.className = 'panel-body';
    panel.appendChild(tabs); panel.appendChild(body);

    async function renderUsers(){
      body.innerHTML = '';
      const list = (users && users.users) || [];
      list.forEach(u=>{
        const row = document.createElement('div'); row.className = 'item-row';
        row.innerHTML = `<div><strong>${escapeHtml(u.username||u.email||('user'+u.id))}</strong><div class="meta">id: ${u.id}</div></div>`;
        const actions = document.createElement('div'); actions.className='actions';
        const banBtn = document.createElement('button'); banBtn.className='btn'; banBtn.textContent='Ban';
        banBtn.addEventListener('click', async ()=>{
          const ok = await confirmModal('Ban user', `Ban ${escapeHtml(u.username||u.email||u.id)}?`);
          if(!ok) return; const resp = await fetchJSON('/admin/ban_user', {method:'POST', body: JSON.stringify({user_id: u.id}), headers:{'Content-Type':'application/json'}});
          if(resp) { showToast('User banned','success'); openAdminPanel(); } else showToast('Failed to ban','error');
        });
        const adminBtn = document.createElement('button'); adminBtn.className='btn'; adminBtn.textContent = u.is_admin? 'Revoke admin':'Make admin';
        adminBtn.addEventListener('click', async ()=>{
          const action = u.is_admin? 'Revoke admin':'Make admin';
          const ok = await confirmModal(action, `${action} for ${escapeHtml(u.username||u.email||u.id)}?`);
          if(!ok) return; const endpoint = u.is_admin? '/admin/revoke_admin':'/admin/make_admin'; const res = await fetchJSON(endpoint, {method:'POST', body: JSON.stringify({user_id: u.id}), headers:{'Content-Type':'application/json'}});
          if(res){ showToast(action + ' successful','success'); openAdminPanel(); } else showToast(action + ' failed','error');
        });
        const del = document.createElement('button'); del.className='btn btn-danger'; del.textContent='Delete';
        del.addEventListener('click', async ()=>{
          const ok = await confirmModal('Delete user', `Delete ${escapeHtml(u.username||u.email||u.id)}? This cannot be undone.`);
          if(!ok) return; const res = await fetchJSON('/admin/users/delete', {method:'POST', body: JSON.stringify({id: u.id}), headers:{'Content-Type':'application/json'}});
          if(res){ showToast('User deleted','success'); openAdminPanel(); } else showToast('Failed to delete','error');
        });
        actions.appendChild(banBtn); actions.appendChild(adminBtn); actions.appendChild(del);
        row.appendChild(actions); body.appendChild(row);
      });
    }

    async function renderBanned(){ body.innerHTML = ''; const list = (banned && banned.banned) || []; if(list.length === 0){ body.innerHTML = '<div class="admin-empty">No banned users</div>'; return } list.forEach(b=>{ const row = document.createElement('div'); row.className='item-row'; row.innerHTML = `<div><strong>${escapeHtml(b.username||b.email||('user'+b.banned_id))}</strong><div class="meta">id: ${b.banned_id}</div></div>`; const actions = document.createElement('div'); actions.className='actions'; const unban = document.createElement('button'); unban.className='btn'; unban.textContent='Unban'; unban.addEventListener('click', async ()=>{ const ok = await confirmModal('Unban user', `Unban ${escapeHtml(b.username||b.email||b.banned_id)}?`); if(!ok) return; const res = await fetchJSON('/admin/unban_user', {method:'POST', body: JSON.stringify({user_id: b.banned_id}), headers:{'Content-Type':'application/json'}}); if(res){ showToast('User unbanned','success'); openAdminPanel(); } else showToast('Failed to unban','error'); }); actions.appendChild(unban); row.appendChild(actions); body.appendChild(row); }); }

    async function renderRooms(){ body.innerHTML = ''; const list = (rooms && rooms.rooms) || []; if(list.length === 0){ body.innerHTML = '<div class="admin-empty">No rooms found</div>'; return } list.forEach(r=>{ const row = document.createElement('div'); row.className='item-row'; row.innerHTML = `<div><strong>${escapeHtml(r.name||('room'+r.id))}</strong><div class="meta">id: ${r.id}</div></div>`; const actions = document.createElement('div'); actions.className='actions'; const del = document.createElement('button'); del.className='btn btn-danger'; del.textContent='Delete room'; del.addEventListener('click', async ()=>{ const ok = await confirmModal('Delete room', `Delete room ${escapeHtml(r.name||r.id)}? This cannot be undone.`); if(!ok) return; const res = await fetchJSON('/admin/delete_room', {method:'POST', body: JSON.stringify({room_id: r.id}), headers:{'Content-Type':'application/json'}}); if(res){ showToast('Room deleted','success'); openAdminPanel(); } else showToast('Failed to delete room','error'); }); actions.appendChild(del); row.appendChild(actions); body.appendChild(row); }); }

    tabUsers.addEventListener('click', ()=>{ tabUsers.classList.add('active'); tabBanned.classList.remove('active'); tabRooms.classList.remove('active'); renderUsers(); });
    tabBanned.addEventListener('click', ()=>{ tabUsers.classList.remove('active'); tabBanned.classList.add('active'); tabRooms.classList.remove('active'); renderBanned(); });
    tabRooms.addEventListener('click', ()=>{ tabUsers.classList.remove('active'); tabBanned.classList.remove('active'); tabRooms.classList.add('active'); renderRooms(); });

    // initial
    renderUsers();
    // dismiss helper
    const closeWrap = document.createElement('div'); closeWrap.style.marginTop='12px'; const closeBtn = document.createElement('button'); closeBtn.className='btn'; closeBtn.textContent='Close'; closeBtn.addEventListener('click', ()=> root.innerHTML=''); closeWrap.appendChild(closeBtn); panel.appendChild(closeWrap);
    root.appendChild(panel);
  }

  // expose globally
  window.openAdminPanel = openAdminPanel;
})();
