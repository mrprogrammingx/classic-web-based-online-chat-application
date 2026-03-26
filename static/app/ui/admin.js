// Admin fallback UI (moved out of app.js)
(function(){
  async function openAdminPanel(){
    try{
      const panel = await (window.fetchJSON ? window.fetchJSON('/admin/users') : fetch('/admin/users').then(r=>r.ok? r.json(): null));
      const users = (panel && panel.users) || [];
      const root = document.getElementById('modal-root') || (function(){ const r=document.createElement('div'); r.id='modal-root'; document.body.appendChild(r); return r; })();
      root.innerHTML = '';
      const p = document.createElement('div'); p.className = 'admin-panel';
      const ul = document.createElement('ul'); ul.style.listStyle='none'; ul.style.padding='0';
      users.forEach(u=>{ const li = document.createElement('li'); li.textContent = `${u.id} - ${u.email}`; ul.appendChild(li); });
      p.appendChild(ul);
      root.appendChild(p);
      return true;
    }catch(e){ console.warn('openAdminPanel fallback failed', e); return false; }
  }

  try{ window.openAdminPanel = openAdminPanel; }catch(e){}
})();
