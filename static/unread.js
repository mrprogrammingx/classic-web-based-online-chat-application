// Shared unread panel helper used by app.js and main.js
(function(){
  function esc(s){ return (window.escapeHtml && typeof window.escapeHtml === 'function') ? window.escapeHtml(s) : (String(s||'').replace(/[&<>'"]/g, function(c){ return ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":"&#39;"})[c]; })); }

  async function openUnreadPanel(){
    try{
      const BASE = location.origin;
      const r = await fetch(BASE + '/notifications/unread-summary', {credentials: 'include'}).catch(()=>null);
      const data = r && r.ok ? await r.json().catch(()=>({})) : {};
      const rooms = (data && data.rooms) || [];
      const dialogs = (data && data.dialogs) || [];
      // remove any existing panel
      const existing = document.querySelector('.unread-panel'); if(existing) existing.remove();
      const panel = document.createElement('div'); panel.className = 'unread-panel';
      const title = document.createElement('h4'); title.textContent = 'Unread notifications';
      const list = document.createElement('ul');
      rooms.forEach(rm => { const li = document.createElement('li'); li.innerHTML = `<span>${esc(rm.room_name||rm.room_id)}</span><strong>${Number(rm.unread_count)||0}</strong>`; list.appendChild(li); });
      dialogs.forEach(d => { const li = document.createElement('li'); li.innerHTML = `<span>${esc(d.other_name||d.other_id)}</span><strong>${Number(d.unread_count)||0}</strong>`; list.appendChild(li); });
      if(!rooms.length && !dialogs.length){ const li = document.createElement('li'); li.textContent = 'No unread messages'; list.appendChild(li); }
      const actions = document.createElement('div'); actions.className = 'panel-actions';
      const openBtn = document.createElement('button'); openBtn.type='button'; openBtn.className='open-btn'; openBtn.textContent='Open notifications page';
      actions.appendChild(openBtn);
      panel.appendChild(title); panel.appendChild(list); panel.appendChild(actions);
      try{ document.body.appendChild(panel); }catch(e){ const container = document.getElementById('notifications') || document.querySelector('.nav-notifications'); if(container && container.parentNode) container.parentNode.appendChild(panel); }
      function cleanupPanel(){ const p = document.querySelector('.unread-panel'); if(p) p.remove(); document.removeEventListener('click', onDocClick); document.removeEventListener('keydown', onKeyDown); }
      function onDocClick(ev){ const p = document.querySelector('.unread-panel'); if(!p) return; if(p.contains(ev.target)) return; if(ev.target && ev.target.id === 'unread-total') return; cleanupPanel(); }
      function onKeyDown(ev){ if(ev.key === 'Escape') cleanupPanel(); }
      setTimeout(()=>{ document.addEventListener('click', onDocClick); document.addEventListener('keydown', onKeyDown); }, 10);
      openBtn.addEventListener('click', ()=>{ cleanupPanel(); location.href = '/static/home.html'; });
    }catch(e){ try{ location.href = '/static/home.html'; }catch(e){} }
  }

  function attachUnreadHandlers(){
    try{
      const btn = document.getElementById('unread-total');
      if(btn){ try{ btn.removeEventListener('click', openUnreadPanel); }catch(e){} btn.addEventListener && btn.addEventListener('click', openUnreadPanel); }
    }catch(e){}
  }

  // expose globally
  window.openUnreadPanel = openUnreadPanel;
  window.attachUnreadHandlers = attachUnreadHandlers;
})();
