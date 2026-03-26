// Admin helpers (small fallback implementations)
(function(){
  const BASE = location.origin;

  async function openAdmin(){
    try{
      const r = await fetch(BASE + '/admin/users', {headers:{'Authorization':'Bearer ' + ((window.appState && window.appState.token) || '')}});
      if(r.status === 403){ window.showToast && window.showToast('admin required','error'); return; }
      const data = await r.json();
      const ul = document.getElementById('admin-users'); if(!ul) return;
      ul.innerHTML = '';
      for(const u of data.users){
        const li = document.createElement('li'); li.textContent = `${u.id} - ${u.email} - ${u.username} - admin:${u.is_admin}`;
        const btn = document.createElement('button'); btn.textContent = 'Delete'; btn.onclick = async ()=>{ await fetch(BASE + '/admin/users/delete', {method:'POST', headers:{'Content-Type':'application/json','Authorization':'Bearer ' + ((window.appState && window.appState.token) || '')}, body: JSON.stringify({id: u.id})}); openAdmin(); };
        li.appendChild(btn); ul.appendChild(li);
      }
      const m = document.getElementById('admin-modal'); if(m) m.style.display = 'block';
    }catch(e){ console.error('openAdmin error', e); }
  }

  try{ window.openAdmin = openAdmin; }catch(e){}
})();
