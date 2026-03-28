// User/session rendering and admin panel helpers (extracted from app.js)
(function(){
  function escapeHtml(s){ return String(s||'').replace(/[&<>'"]/g, c=>({ '&':'&amp;','<':'&lt;','>':'&gt;',"'":"&#39;", '"':'&quot;' })[c]); }
  async function loadSessions(){
    try{
      console.debug && console.debug('sessions: loadSessions called...');
      // If the home page right-side container exists, prefer rendering into
      // it so the sessions list appears in the page where the user clicked.
      // Otherwise fall back to the header dropdown's #sessions-list.
      const rightContainer = document.getElementById('sessions');
      let sessionsList = null;
      if(rightContainer){
        sessionsList = rightContainer.querySelector('#sessions-list');
        if(!sessionsList){
          const ul = document.createElement('ul');
          ul.id = 'sessions-list';
          ul.className = 'sessions-list';
          rightContainer.innerHTML = ''; // clear placeholder
          rightContainer.appendChild(ul);
          sessionsList = ul;
        }
      } else {
        sessionsList = document.getElementById('sessions-list');
      }
      if(!sessionsList) return;
      sessionsList.innerHTML = '<li class="meta">Loading…</li>';
      console.debug && console.debug('Pre data:');

      // Wrap fetchJSON in a timeout so the UI doesn't hang indefinitely if
      // the request stalls. Prefer the global window.fetchJSON helper when
      // available; otherwise fall back to a small inline implementation.
      const timeoutMs = 8000;
      const fetcher = (typeof window !== 'undefined' && typeof window.fetchJSON === 'function') ? window.fetchJSON : async function(url, opts){
        try{
          opts = opts || {};
          if(typeof opts.credentials === 'undefined') opts.credentials = 'include';
          opts.headers = opts.headers || {};
          const r = await fetch(url, opts);
          if(!r.ok){ console.warn('fetch failed (fallback)', url, r.status); return null; }
          return await r.json().catch(()=>null);
        }catch(e){ console.warn('fetchJSON fallback failed', e); return null; }
      };

      let data = null;
      try{
        data = await Promise.race([
          fetcher('/sessions'),
          new Promise((_, rej) => setTimeout(() => rej(new Error('fetch timeout')), timeoutMs))
        ]);
        console.debug && console.debug('data:', data);
      }catch(e){
        console.debug && console.debug('sessions: fetch error', e);
        try{ sessionsList.innerHTML = '<li class="meta">Error loading sessions</li>'; }catch(_){ }
        return;
      }

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
      // Always create the badge element for a stable DOM structure; show it
      // only when the user.is_admin flag is truthy.
      try{
        const badge = document.createElement('span'); badge.className = 'badge'; badge.textContent = 'admin';
        if(!user || !user.is_admin) badge.style.display = 'none';
        toggle.appendChild(badge);
      }catch(e){}
      const panel = document.createElement('div'); panel.className = 'dropdown-panel'; panel.id = 'user-panel'; panel.style.display = 'none';
      const h4 = document.createElement('h4'); h4.textContent = 'Sessions';
      const sessionsList = document.createElement('ul'); sessionsList.className = 'sessions-list'; sessionsList.id = 'sessions-list'; sessionsList.innerHTML = '<li class="meta">Loading…</li>';
  const footer = document.createElement('div'); footer.style.marginTop = '8px'; footer.style.display = 'flex'; footer.style.gap = '8px'; footer.style.justifyContent = 'space-between';
  const changeBtn = document.createElement('button'); changeBtn.id = 'btn-change-password-inline'; changeBtn.type = 'button'; changeBtn.textContent = 'Change password';
  const logoutBtn = document.createElement('button'); logoutBtn.id = 'btn-logout-inline'; logoutBtn.type = 'button'; logoutBtn.textContent = 'Logout';
  const deleteBtn = document.createElement('button'); deleteBtn.id = 'btn-delete-account-inline'; deleteBtn.type = 'button'; deleteBtn.textContent = 'Delete account'; deleteBtn.style.background = '#b33'; deleteBtn.style.color = '#fff';
  const refreshBtn = document.createElement('button'); refreshBtn.id = 'btn-refresh-sessions'; refreshBtn.type = 'button'; refreshBtn.textContent = 'Refresh';
  footer.appendChild(changeBtn); footer.appendChild(logoutBtn); footer.appendChild(deleteBtn); footer.appendChild(refreshBtn);
  try{ if(logoutBtn && logoutBtn.addEventListener){ logoutBtn.addEventListener('click', function(ev){ ev.preventDefault(); try{ fetch('/logout', { method: 'POST', credentials: 'same-origin' }).then(function(){ window.location = '/'; }).catch(function(){ window.location = '/'; }); }catch(e){ window.location = '/'; } }); } }catch(e){}
  try{ if(deleteBtn && deleteBtn.addEventListener){ deleteBtn.addEventListener('click', async function(ev){ ev.preventDefault(); try{
        // Confirm via centralized modal if available
        let confirmed = false;
        if(window.showModal){
          const body = document.createElement('div');
          body.style.display='flex'; body.style.flexDirection='column'; body.style.gap='8px';
          const p = document.createElement('div'); p.textContent = 'Delete your account and all associated data. This action is irreversible.';
          body.appendChild(p);
          const forced = document.createElement('div'); forced.style.fontSize='12px'; forced.style.opacity='0.9'; forced.textContent = 'Type DELETE to confirm:';
          const input = document.createElement('input'); input.placeholder = 'DELETE'; input.id = 'confirm-delete-input';
          body.appendChild(forced); body.appendChild(input);
          const opts = { title: 'Delete account', body: body, confirmText: 'Delete', cancelText: 'Cancel', html: true,
            getResult: function(){ return { typed: (document.getElementById('confirm-delete-input') && document.getElementById('confirm-delete-input').value) || '' }; }
          };
          const res = await window.showModal(opts);
          if(!res) return;
          const typed = (typeof res === 'object' && res !== null) ? res.typed : (document.getElementById('confirm-delete-input') && document.getElementById('confirm-delete-input').value) || '';
          if(String(typed).trim() !== 'DELETE'){
            return window.showToast && window.showToast('Type DELETE to confirm account deletion','error');
          }
          confirmed = true;
        } else {
          confirmed = confirm('Delete your account and all associated data? This is irreversible.');
        }
        if(!confirmed) return;
        deleteBtn.disabled = true;
        const r = await fetch('/me', { method: 'DELETE', credentials: 'include' });
        if(r && r.ok){ window.showToast && window.showToast('Account deleted','success'); window.location = '/static/auth/login.html'; }
        else { deleteBtn.disabled = false; let body = null; try{ body = await r.json(); }catch(e){ try{ body = await r.text(); }catch(_){ body = null; } } const msg = body ? (typeof body === 'string' ? body : JSON.stringify(body)) : 'Failed to delete account'; window.showToast && window.showToast(msg,'error'); }
      }catch(e){ console.warn('delete account failed', e); deleteBtn.disabled = false; window.showToast && window.showToast('Failed to delete account','error'); } }); } }catch(e){}
      panel.appendChild(h4); panel.appendChild(sessionsList); panel.appendChild(footer);
      dropdown.appendChild(toggle); dropdown.appendChild(panel); ui.appendChild(dropdown);
  function closePanel(){ if(panel) panel.style.display='none'; }
  function openPanel(){ if(panel) panel.style.display='block'; loadSessions(); }
  if(toggle) toggle.addEventListener('click', ()=>{ if(panel && panel.style.display==='block') closePanel(); else openPanel(); });
  if(refreshBtn) refreshBtn.addEventListener('click', ()=> loadSessions());
  if(document.getElementById('btn-change-password-inline')){
    try{ document.getElementById('btn-change-password-inline').addEventListener('click', ()=>{ try{ if(typeof window.changePasswordUI === 'function') window.changePasswordUI(); }catch(e){} }); }catch(e){}
  }
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
    // wire change-password button in rightbar/home if present
    try{ var cp = document.getElementById('change-password'); if(cp){ cp.addEventListener && cp.addEventListener('click', async ()=>{ try{ if(typeof window.changePasswordUI === 'function') return window.changePasswordUI(); }catch(e){} }); } }catch(e){}
  }

  // change password UI helper
  async function changePasswordUI(){
    try{
      // prefer centralized showModal if available
      if(window.showModal){
  // build a DOM node for the modal body so inputs are real elements
  const bodyNode = document.createElement('div');
  bodyNode.style.display = 'flex'; bodyNode.style.flexDirection = 'column'; bodyNode.style.gap = '8px';
  const inCurrent = document.createElement('input'); inCurrent.type = 'password'; inCurrent.id = 'cp-current'; inCurrent.placeholder = 'current password';
  const inNew = document.createElement('input'); inNew.type = 'password'; inNew.id = 'cp-new'; inNew.placeholder = 'new password';
  bodyNode.appendChild(inCurrent); bodyNode.appendChild(inNew);
        const opts = { title: 'Change password', body: bodyNode, confirmText: 'Change', cancelText: 'Cancel', html: true,
          // getResult will be called by showModal before it removes the modal
          getResult: function(){ return { current: (document.getElementById('cp-current') && document.getElementById('cp-current').value) || null, newpw: (document.getElementById('cp-new') && document.getElementById('cp-new').value) || null }; }
        };
        const okOrResult = await window.showModal(opts);
        // if the resolved value is falsy, treat as cancel
        if(!okOrResult){ try{ inCurrent.value = ''; inNew.value = ''; }catch(e){}; return; }
        // showModal will return either true or a value; if it's an object from getResult, use it
        const res = (typeof okOrResult === 'object' && okOrResult !== null) ? okOrResult : { current: (document.getElementById('cp-current') && document.getElementById('cp-current').value) || null, newpw: (document.getElementById('cp-new') && document.getElementById('cp-new').value) || null };
        const current = res.current;
        const newpw = res.newpw;
  if(!current || !newpw){ try{ inCurrent.value = ''; inNew.value = ''; }catch(e){}; return window.showToast && window.showToast('Both passwords required','error'); }
        const r = await fetch('/me/password', {method:'PATCH', credentials:'include', headers: {'Content-Type':'application/json'}, body: JSON.stringify({current_password: current, new_password: newpw})});
  try{
    if(r && r.ok){ window.showToast && window.showToast('Password changed','success'); }
    else {
      // attempt to show server-provided detail
      let body = null;
      try{ body = await r.json(); }catch(e){ try{ body = await r.text(); }catch(_){ body = null; } }
      const msg = body ? (typeof body === 'string' ? body : JSON.stringify(body)) : 'Failed to change password';
      window.showToast && window.showToast(msg,'error');
    }
  }finally{ try{ inCurrent.value = ''; inNew.value = ''; }catch(e){} }
  return;
      }
      // fallback simple prompts
      const current = prompt('Current password:'); if(!current) return;
      const newpw = prompt('New password:'); if(!newpw) return;
      const r2 = await fetch('/me/password', {method:'PATCH', credentials:'include', headers: {'Content-Type':'application/json'}, body: JSON.stringify({current_password: current, new_password: newpw})});
      if(r2 && r2.ok) alert('Password changed'); else alert('Failed to change password');
    }catch(e){ console.warn('changePasswordUI failed', e); }
  }

  function openAdminPanel(){ try{ if(typeof window.openAdminPanel === 'function') return window.openAdminPanel(); /* fallback not implemented here */ }catch(e){} }

  try{ window.loadSessions = loadSessions; window.renderUserInfo = renderUserInfo; window.openAdminPanel = openAdminPanel; window.initSessionsUi = initSessionsUi; window.changePasswordUI = changePasswordUI; }catch(e){}
  // If the header was already populated by a minimal fallback (main.js/bootstrap),
  // try to upgrade it now that the sessions lib is available by fetching /me
  // and calling the richer renderUserInfo() implementation.
    async function tryUpgradeHeader(){
      try{
        console.debug && console.debug('sessions: tryUpgradeHeader running');
        if(!document.getElementById('user-info')) return;
  // best-effort fetch current user. Prefer Authorization header when a
  // token is available in JS (window.appState.token or sessionStorage.boot_token),
  // but still include credentials so cookie-based sessions continue to work.
  const headers = {};
  try{ const t = (window && window.appState && window.appState.token) || (sessionStorage && sessionStorage.getItem && sessionStorage.getItem('boot_token')); if(t) headers['Authorization'] = 'Bearer ' + t; }catch(e){}
  const opts = { credentials: 'include', headers };
  const r = await fetch('/me', opts).catch(()=>null);
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
