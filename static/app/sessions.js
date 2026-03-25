// User/session rendering and admin panel helpers (extracted from app.js)
(function(){
  async function loadSessions(){
    try{
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
      const ui = document.getElementById('user-info');
      if(!ui) return;
      const display = (user.username || user.email || ('user'+user.id));
      ui.innerHTML = `\n+            <div class="user-dropdown">\n+              <div class="user-toggle" id="user-toggle" tabindex="0">\n+                <span class="avatar">${String((user.username||user.email||'U').charAt(0)).toUpperCase()}</span>\n+                <strong>${escapeHtml(display)}</strong>\n+                ${user.is_admin? '<span class="badge">admin</span>':''}\n+              </div>\n+              <div class="dropdown-panel" id="user-panel" style="display:none">\n+                <h4>Sessions</h4>\n+                <ul class="sessions-list" id="sessions-list"><li class="meta">Loading…</li></ul>\n+                <div style="margin-top:8px;display:flex;gap:8px;justify-content:space-between">\n+                  <button id="btn-logout-inline" type="button">Logout</button>\n+                  <button id="btn-refresh-sessions" type="button">Refresh</button>\n+                </div>\n+              </div>\n+            </div>\n+          `;
      const toggle = document.getElementById('user-toggle');
      const panel = document.getElementById('user-panel');
      const sessionsList = document.getElementById('sessions-list');
      const refreshBtn = document.getElementById('btn-refresh-sessions');
      const inlineLogout = document.getElementById('btn-logout-inline');
      function closePanel(){ if(panel) panel.style.display='none'; }
      function openPanel(){ if(panel) panel.style.display='block'; loadSessions(); }
      if(toggle) toggle.addEventListener('click', ()=>{ if(panel && panel.style.display==='block') closePanel(); else openPanel(); });
      if(refreshBtn) refreshBtn.addEventListener('click', ()=> loadSessions());
      if(inlineLogout) inlineLogout.addEventListener('click', async ()=>{ try{ await fetch('/logout', {method:'POST', credentials:'include'}); }catch(e){} location.href='/static/auth/login.html'; });
      // show admin button (header may add admin-open elsewhere)
      try{ const adminBtn = document.getElementById('admin-open'); if(adminBtn) adminBtn.style.display = user.is_admin ? 'inline-flex' : 'none'; }catch(e){}
    }catch(e){ console.warn('renderUserInfo failed', e); }
  }

  function openAdminPanel(){ try{ if(typeof window.openAdminPanel === 'function') return window.openAdminPanel(); /* fallback not implemented here */ }catch(e){} }

  try{ window.loadSessions = loadSessions; window.renderUserInfo = renderUserInfo; window.openAdminPanel = openAdminPanel; }catch(e){}
})();
