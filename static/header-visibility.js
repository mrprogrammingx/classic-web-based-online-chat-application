// header-visibility.js
// Small helper to ensure admin button visibility as soon as header is present.
(async function(){
  'use strict';
  async function maybeRevealAdmin(){
    try{
      const adminBtn = document.getElementById('admin-open'); if(!adminBtn) return;
      let user = null;
      try{ const raw = sessionStorage.getItem('boot_user'); if(raw) user = JSON.parse(raw); }catch(e){}
      if(!user){
        try{ const r = await fetch('/me', { credentials: 'include' }); if(r && r.ok){ const j = await r.json().catch(()=>null); if(j && j.user) user = j.user; } }catch(e){}
      }
      if(user && user.is_admin) adminBtn.style.display = 'inline-flex';
    }catch(e){ /* ignore */ }
  }

  // run now and also after header loads
  try{ maybeRevealAdmin(); }catch(e){}
  window.addEventListener('shared-header-loaded', maybeRevealAdmin);
})();
