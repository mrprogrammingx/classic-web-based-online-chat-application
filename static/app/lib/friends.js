// Friends and incoming-requests helpers (extracted from main.js)
(function(){
  // Use an explicit API base when provided (useful in tests/dev). Otherwise
  // default to the relative root so requests go to the same server that
  // served the page (avoids cross-port issues when opening files via a
  // different dev server on another port).
  const BASE = (typeof window !== 'undefined' && window.API_BASE) ? window.API_BASE : '';

  async function loadFriends(){
    try{
      const r = await fetch(BASE + '/friends', {credentials: 'include', headers: window.authHeaders ? window.authHeaders() : {}});
      if(r.status !== 200) return;
      const data = await r.json();
      // Store globally so UI modules can read and render regardless of load order
      try{ window.contacts = data.friends || []; }catch(e){}
      // If a UI renderer is present (contacts-ui), prefer it to render the list
      if(window && typeof window.renderFriendsList === 'function'){
        try{ window.renderFriendsList(); return; }catch(e){ /* fall through to default rendering on error */ }
      }
      const ul = document.getElementById('friends-list'); if(!ul) return;
      ul.innerHTML = '';
      for(const f of data.friends){
        const li = document.createElement('li');
        li.innerHTML = `<span style="display:inline-block;width:10px;height:10px;border-radius:50%;background:gray;margin-right:8px;vertical-align:middle" id="friend-dot-${f.id}"></span> ${f.username} (${f.email}) <button data-id="${f.id}" class="remove-btn">Remove</button> <button data-id="${f.id}" class="ban-btn">Ban</button>`;
        const btn = li.querySelector('.remove-btn');
        btn.onclick = async ()=>{ try{ btn.disabled = true; const r = await fetch(BASE + '/friends/remove', {method:'POST', credentials: 'include', headers: window.authHeaders ? window.authHeaders('application/json') : {'Content-Type':'application/json'}, body: JSON.stringify({friend_id: f.id})}); if(r.status===200) await loadFriends(); else { const body = await r.json().catch(()=>null); window.showStatus && window.showStatus('Failed: ' + JSON.stringify(body)); window.showToast && window.showToast(JSON.stringify(body), 'error'); } }catch(e){ window.showToast && window.showToast('failed to remove', 'error') } finally{ btn.disabled = false } }
        const banBtn = li.querySelector('.ban-btn');
        banBtn.onclick = async ()=>{ try{ const ok = await (window.showModal ? window.showModal({title: 'Ban user', body: 'Ban this user? This action cannot be undone.', confirmText: 'Ban', cancelText: 'Keep'}) : Promise.resolve(confirm('Ban this user?'))); if(!ok) return; banBtn.disabled = true; const r = await fetch(BASE + '/ban', {method:'POST', credentials: 'include', headers: window.authHeaders ? window.authHeaders('application/json') : {'Content-Type':'application/json'}, body: JSON.stringify({banned_id: f.id})}); if(r.status===200) await loadFriends(); else { const body = await r.json().catch(()=>null); window.showStatus && window.showStatus('Failed: ' + JSON.stringify(body)); window.showToast && window.showToast(JSON.stringify(body), 'error'); } }catch(e){ window.showToast && window.showToast('failed to ban', 'error') } finally{ banBtn.disabled = false } }
        ul.appendChild(li);
        (async (fid)=>{ try{ const r2 = await fetch(BASE + '/presence/' + fid); if(r2.status !== 200) return; const d = await r2.json(); const dot = document.getElementById('friend-dot-' + fid); if(dot){ const s = (d.status || '').toLowerCase(); if(s === 'online') dot.style.background = 'green'; else if(s === 'afk') dot.style.background = 'orange'; else dot.style.background = 'gray'; } }catch(e){} })(f.id);
      }
    }catch(e){ console.warn('failed to load friends', e) }
  }

  async function loadIncomingRequests(){
    try{
      const r = await fetch(BASE + '/friends/requests', {credentials: 'include', headers: window.authHeaders ? window.authHeaders() : {}});
      if(r.status !== 200) return;
      const data = await r.json();
      const ul = document.getElementById('incoming-requests'); if(!ul) return;
      ul.innerHTML = '';
      for(const rq of data.requests){
        const li = document.createElement('li');
        li.textContent = `${rq.username} (${rq.email}) - ${rq.message || ''}`;
        const accept = document.createElement('button'); accept.textContent = 'Accept';
        accept.onclick = async ()=>{ try{ accept.disabled = true; const r = await fetch(BASE + '/friends/requests/respond', {method:'POST', credentials: 'include', headers: window.authHeaders ? window.authHeaders('application/json') : {'Content-Type':'application/json'}, body: JSON.stringify({request_id: rq.id, action: 'accept'})}); if(r.status===200){ await loadIncomingRequests(); await loadFriends(); window.showStatus && window.showStatus('Accepted'); } else { const body = await r.json().catch(()=>null); window.showStatus && window.showStatus('Failed: ' + JSON.stringify(body)); window.showToast && window.showToast(JSON.stringify(body), 'error'); } }catch(e){ window.showToast && window.showToast('failed to accept', 'error') } finally{ accept.disabled = false } }
        const reject = document.createElement('button'); reject.textContent = 'Reject';
        reject.onclick = async ()=>{ try{ reject.disabled = true; const r = await fetch(BASE + '/friends/requests/respond', {method:'POST', credentials: 'include', headers: window.authHeaders ? window.authHeaders('application/json') : {'Content-Type':'application/json'}, body: JSON.stringify({request_id: rq.id, action: 'reject'})}); if(r.status===200) await loadIncomingRequests(); else { const body = await r.json().catch(()=>null); window.showStatus && window.showStatus('Failed: ' + JSON.stringify(body)); window.showToast && window.showToast(JSON.stringify(body), 'error'); } }catch(e){ window.showToast && window.showToast('failed to reject', 'error') } finally{ reject.disabled = false } }
        const ban = document.createElement('button'); ban.textContent = 'Ban';
        ban.onclick = async ()=>{ try{ const ok = await (window.showModal ? window.showModal({title: 'Ban user', body: 'Ban this user? This action cannot be undone.', confirmText: 'Ban', cancelText: 'Keep'}) : Promise.resolve(confirm('Ban this user?'))); if(!ok) return; ban.disabled = true; const r = await fetch(BASE + '/ban', {method:'POST', credentials: 'include', headers: window.authHeaders ? window.authHeaders('application/json') : {'Content-Type':'application/json'}, body: JSON.stringify({banned_id: rq.from_id})}); if(r.status===200){ await loadIncomingRequests(); await loadFriends(); window.showStatus && window.showStatus('Banned'); } else { const body = await r.json().catch(()=>null); window.showStatus && window.showStatus('Failed: ' + JSON.stringify(body)); window.showToast && window.showToast(JSON.stringify(body), 'error'); } }catch(e){ window.showToast && window.showToast('failed to ban', 'error') } finally{ ban.disabled = false } }
        li.appendChild(accept); li.appendChild(reject); li.appendChild(ban);
        ul.appendChild(li);
      }
    }catch(e){ console.warn('failed to load incoming requests', e) }
  }

  try{ window.loadFriends = loadFriends; window.loadIncomingRequests = loadIncomingRequests; }catch(e){}
  
  async function loadBannedUsers(){
    try{
      const r = await fetch(BASE + '/bans', {credentials: 'include', headers: window.authHeaders ? window.authHeaders() : {}});
      if(r.status !== 200) return;
      const data = await r.json();
      const ul = document.getElementById('banned-users'); if(!ul) return;
      ul.innerHTML = '';
      for(const b of (data.banned || [])){
        const li = document.createElement('li');
        li.innerHTML = `${b.username || b.email || ('user'+b.banned_id)} <button data-id="${b.banned_id}" class="unban-btn">Unban</button>`;
        const btn = li.querySelector('.unban-btn');
        btn.onclick = async ()=>{ try{ btn.disabled = true; const r = await fetch(BASE + '/unban', {method:'POST', credentials:'include', headers: window.authHeaders ? window.authHeaders('application/json') : {'Content-Type':'application/json'}, body: JSON.stringify({banned_id: b.banned_id})}); if(r.status===200){ await loadBannedUsers(); window.showToast && window.showToast('Unbanned','success'); } else { const body = await r.json().catch(()=>null); window.showToast && window.showToast(JSON.stringify(body),'error'); } }catch(e){ window.showToast && window.showToast('failed to unban','error') } finally{ btn.disabled = false } }
        ul.appendChild(li);
      }
    }catch(e){ console.warn('failed to load banned users', e) }
  }
  try{ window.loadBannedUsers = loadBannedUsers; }catch(e){}
})();
