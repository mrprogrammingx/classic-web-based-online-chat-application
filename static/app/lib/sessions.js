// User/session rendering and admin panel helpers (extracted from app.js)
(function(){
  function escapeHtml(s){ return String(s||'').replace(/[&<>'"]/g, c=>({ '&':'&amp;','<':'&lt;','>':'&gt;',"'":"&#39;", '"':'&quot;' })[c]); }
  async function loadSessions(){
    try{
      console.debug && console.debug('sessions: loadSessions called');
      const sessionsList = document.getElementById('sessions-list');
      if(!sessionsList) return;
      sessionsList.innerHTML = '<li class="meta">Loading…</li>';
      const data = await window.fetchJSON('/sessions');
      if(!data || !data.sessions) return sessionsList.innerHTML = '<li class="meta">No sessions</li>';
      sessionsList.innerHTML = '';
      data.sessions.forEach(s => {
        const li = document.createElement('li');
        const meta = document.createElement('div'); meta.className='meta'; meta.textContent = `jti: ${s.jti} • last active: ${new Date((s.last_active||s.created_at||0)*1000).toLocaleString()}`;
        const btn = document.createElement('button'); btn.type='button'; btn.textContent='Revoke';
        btn.addEventListener('click', async ()=>{
          const ok = await (window.showModal ? window.showModal({title:'Revoke session', body:'Revoke this session? This will immediately log out that session.', confirmText:'Revoke', cancelText:'Keep'}) : Promise.resolve(confirm('Revoke this session?')));
          if(!ok) return;
          try{
            btn.disabled = true;
            const r = await fetch('/sessions/revoke', {method:'POST', credentials:'include', headers:{'Content-Type':'application/json'}, body: JSON.stringify({jti: s.jti})});
            if(r && r.ok){ li.style.transition = 'opacity 220ms'; li.style.opacity = '0'; setTimeout(()=>{ li.remove(); window.showToast && window.showToast('Session revoked','success'); }, 260); }
            else { btn.disabled = false; window.showToast && window.showToast('Failed to revoke session','error'); }
          }catch(e){ console.warn('revoke failed', e); btn.disabled = false; window.showToast && window.showToast('Failed to revoke session','error'); }
        });
        li.appendChild(meta); li.appendChild(btn); sessionsList.appendChild(li);
      });
    }catch(e){ try{ document.getElementById('sessions-list').innerHTML = '<li class="meta">Error loading sessions</li>'; }catch(_){} }
  }

  function renderUserInfo(user){
    try{
      console.debug && console.debug('sessions: renderUserInfo called', user && user.username);
      const ui = document.getElementById('user-info');
      if(!ui) return;
      const display = (user.username || user.email || ('user'+user.id));
      // build DOM nodes safely instead of innerHTML templating
      ui.innerHTML = '';
      const dropdown = document.createElement('div'); dropdown.className = 'user-dropdown';
      const toggle = document.createElement('div'); toggle.className = 'user-toggle'; toggle.id = 'user-toggle'; toggle.tabIndex = 0;
      const avatar = document.createElement('span'); avatar.className = 'avatar'; avatar.textContent = String((user.username||user.email||'U').charAt(0)).toUpperCase();
      const strong = document.createElement('strong'); strong.textContent = display;
      toggle.appendChild(avatar); toggle.appendChild(strong);
      if(user.is_admin){ const badge = document.createElement('span'); badge.className = 'badge'; badge.textContent = 'admin'; toggle.appendChild(badge); }
      const panel = document.createElement('div'); panel.className = 'dropdown-panel'; panel.id = 'user-panel'; panel.style.display = 'none';
      const h4 = document.createElement('h4'); h4.textContent = 'Sessions';
      const sessionsList = document.createElement('ul'); sessionsList.className = 'sessions-list'; sessionsList.id = 'sessions-list'; sessionsList.innerHTML = '<li class="meta">Loading…</li>';
      const footer = document.createElement('div'); footer.style.marginTop = '8px'; footer.style.display = 'flex'; footer.style.gap = '8px'; footer.style.justifyContent = 'space-between';
      const logoutBtn = document.createElement('button'); logoutBtn.id = 'btn-logout-inline'; logoutBtn.type = 'button'; logoutBtn.textContent = 'Logout';
      const refreshBtn = document.createElement('button'); refreshBtn.id = 'btn-refresh-sessions'; refreshBtn.type = 'button'; refreshBtn.textContent = 'Refresh';
      footer.appendChild(logoutBtn); footer.appendChild(refreshBtn);
      panel.appendChild(h4); panel.appendChild(sessionsList); panel.appendChild(footer);
      dropdown.appendChild(toggle); dropdown.appendChild(panel); ui.appendChild(dropdown);
  function closePanel(){ if(panel) panel.style.display='none'; }
  function openPanel(){ if(panel) panel.style.display='block'; loadSessions(); }
  if(toggle) toggle.addEventListener('click', ()=>{ if(panel && panel.style.display==='block') closePanel(); else openPanel(); });
  if(refreshBtn) refreshBtn.addEventListener('click', ()=> loadSessions());
      // show admin button (header may add admin-open elsewhere)
      try{ const adminBtn = document.getElementById('admin-open'); if(adminBtn) adminBtn.style.display = user.is_admin ? 'inline-flex' : 'none'; }catch(e){}
    }catch(e){ console.warn('renderUserInfo failed', e); }
  }

  // initialize header/session-related UI wiring (header may be injected later)
  function initSessionsUi(root){
    root = root || document;
    // reattach unread handlers when header fragment loads
    root.addEventListener && root.addEventListener('shared-header-loaded', function(){ try{ if(typeof attachUnreadHandlers === 'function') attachUnreadHandlers(); }catch(e){} });
    // admin open button wiring
    try{ var adminBtn = document.getElementById('admin-open'); if(adminBtn){ adminBtn.addEventListener && adminBtn.addEventListener('click', async ()=>{ try{ if(window && typeof window.openAdminPanel === 'function') return window.openAdminPanel(); }catch(e){} }); } }catch(e){}
  }

  function openAdminPanel(){ try{ if(typeof window.openAdminPanel === 'function') return window.openAdminPanel(); /* fallback not implemented here */ }catch(e){} }

  try{ window.loadSessions = loadSessions; window.renderUserInfo = renderUserInfo; window.openAdminPanel = openAdminPanel; window.initSessionsUi = initSessionsUi; }catch(e){}
  // If the header was already populated by a minimal fallback (main.js/bootstrap),
  // try to upgrade it now that the sessions lib is available by fetching /me
  // and calling the richer renderUserInfo() implementation.
    async function tryUpgradeHeader(){
      try{
        console.debug && console.debug('sessions: tryUpgradeHeader running');
        if(!document.getElementById('user-info')) return;
        // best-effort fetch current user (cookie auth)
        const r = await fetch('/me', { credentials: 'include' }).catch(()=>null);
        console.debug && console.debug('sessions: /me fetch returned', r && r.status);
        if(!r || r.status !== 200) return;
        const body = await r.json().catch(()=>null);
        console.debug && console.debug('sessions: /me body', body);
        if(body && body.user){ try{ renderUserInfo(body.user); }catch(e){} }
      }catch(e){}
    }

    // try immediately, and also after header fragment is injected
    tryUpgradeHeader();
    try{ window.addEventListener && window.addEventListener('shared-header-loaded', tryUpgradeHeader); }catch(e){}
})();
