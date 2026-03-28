(function(){
  const BASE = location.origin;

  // Render contacts (used in chat contacts list)
  function renderContacts(){
    try{
      const list = document.getElementById('contacts-list');
      if(!list) return;
      list.innerHTML = '';
      const items = (window.contacts || []).slice();
      items.forEach(c => {
        const li = document.createElement('li');
        li.dataset.id = String(c.id);
        const dot = document.createElement('span'); dot.className = 'presence-dot'; dot.style.marginRight = '8px'; dot.style.background = 'gray'; dot.id = 'contact-dot-' + c.id;
        const name = document.createElement('span'); name.textContent = c.name || ('user'+c.id);
        li.appendChild(dot); li.appendChild(name);
        li.addEventListener('click', ()=>{ try{ // if we're on the public home page, navigate to the chat page with a dialog param
            if(location && location.pathname === '/static/home.html'){ location.href = '/static/chat/index.html?dialog=' + encodeURIComponent(c.id); return; }
            if(window && typeof window.openDialog === 'function') window.openDialog(c.id);
          }catch(e){} });
        list.appendChild(li);
        // attempt to load presence for contact
        (async (fid)=>{ try{ const r = await fetch(BASE + '/presence/' + fid); if(r.status===200){ const d = await r.json(); const s = (d.status||'').toLowerCase(); const el = document.getElementById('contact-dot-' + fid); if(el){ if(s==='online') el.style.background='green'; else if(s==='afk') el.style.background='orange'; else el.style.background='gray'; } } }catch(e){} })(c.id);
      });
    }catch(e){ console.warn('renderContacts failed', e); }
  }

  // Render friends list (used on home page rightbar)
  async function renderFriendsList(){
    try{
      const ul = document.getElementById('friends-list'); if(!ul) return;
      ul.innerHTML = '';
      const friends = (window.contacts || []).slice();
      for(const f of friends){
        const li = document.createElement('li');
        const dot = document.createElement('span'); dot.style.display='inline-block'; dot.style.width='10px'; dot.style.height='10px'; dot.style.borderRadius='50%'; dot.style.background='gray'; dot.style.marginRight='8px'; dot.id = 'friend-dot-ui-' + f.id;
        const text = document.createElement('span'); text.textContent = (f.username || f.email || ('user'+f.id));
        const remove = document.createElement('button'); remove.textContent = 'Remove'; remove.className = 'remove-btn'; remove.style.marginLeft = '8px';
        const ban = document.createElement('button'); ban.textContent = 'Ban'; ban.className = 'ban-btn'; ban.style.marginLeft = '6px';
        li.appendChild(dot); li.appendChild(text); li.appendChild(remove); li.appendChild(ban);
        remove.addEventListener('click', async (ev)=>{ ev.stopPropagation(); try{ remove.disabled = true; const r = await fetch(BASE + '/friends/remove', { method: 'POST', credentials: 'include', headers: {'Content-Type':'application/json'}, body: JSON.stringify({friend_id: f.id}) }); if(r.status===200){ await window.loadFriends && window.loadFriends(); await window.loadContacts && window.loadContacts(); } else { const b = await r.json().catch(()=>null); window.showToast && window.showToast(JSON.stringify(b),'error'); } }catch(e){ window.showToast && window.showToast('Failed to remove','error'); } finally{ remove.disabled = false } });
        ban.addEventListener('click', async (ev)=>{ ev.stopPropagation(); try{ const ok = window.showModal ? await window.showModal({ title: 'Ban user', body: 'Ban this user?', confirmText: 'Ban', cancelText: 'Keep' }) : confirm('Ban this user?'); if(!ok) return; ban.disabled = true; const r = await fetch(BASE + '/ban', { method: 'POST', credentials: 'include', headers: {'Content-Type':'application/json'}, body: JSON.stringify({banned_id: f.id}) }); if(r.status===200){ await window.loadFriends && window.loadFriends(); await window.loadContacts && window.loadContacts(); window.showToast && window.showToast('Banned','success'); } else { const b = await r.json().catch(()=>null); window.showToast && window.showToast(JSON.stringify(b),'error'); } }catch(e){ window.showToast && window.showToast('Failed to ban','error'); } finally{ ban.disabled = false } });
        li.addEventListener('click', ()=>{ try{ // if we're on the public home page, navigate to the chat page with a dialog param
            if(location && location.pathname === '/static/home.html'){ location.href = '/static/chat/index.html?dialog=' + encodeURIComponent(f.id); return; }
            window.openDialog && window.openDialog(f.id);
          }catch(e){} });
        ul.appendChild(li);
        // presence
        (async (fid)=>{ try{ const r = await fetch(BASE + '/presence/' + fid); if(r.status===200){ const d = await r.json(); const s = (d.status||'').toLowerCase(); const el = document.getElementById('friend-dot-ui-' + fid); if(el){ if(s==='online') el.style.background='green'; else if(s==='afk') el.style.background='orange'; else el.style.background='gray'; } } }catch(e){} })(f.id);
      }
    }catch(e){ console.warn('renderFriendsList failed', e); }
  }

  try{ window.renderContacts = renderContacts; window.renderFriendsList = renderFriendsList; }catch(e){}

  // Also, if loadContacts/loadFriends are already present, attempt to hook into them
  try{ if(typeof window.loadContacts === 'function'){ const orig = window.loadContacts; window.loadContacts = async function(){ await orig(); try{ window.renderContacts && window.renderContacts(); }catch(e){} }; }
  }catch(e){}
  try{ if(typeof window.loadFriends === 'function'){ const orig2 = window.loadFriends; window.loadFriends = async function(){ await orig2(); try{ window.renderFriendsList && window.renderFriendsList(); }catch(e){} }; }
  }catch(e){}

})();
