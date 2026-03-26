// Presence and heartbeat helpers (extracted)
(function(){
  const BASE = location.origin;
  let _presenceInterval = null;

  async function heartbeat(token, jti, tabId){
    if(!token || !jti) return;
    try{ await fetch(BASE + '/presence/heartbeat', {method:'POST', headers:{'content-type':'application/json','Authorization':'Bearer ' + token}, body: JSON.stringify({tab_id: tabId, jti})}); }catch(e){ console.warn('heartbeat failed', e); }
  }

  function startHeartbeat(token, jti, tabId){
    try{ heartbeat(token, jti, tabId); window._hb = setInterval(()=>heartbeat(token, jti, tabId), 20000); }catch(e){}
  }

  function startPresencePolling(userId){
    async function update(){
      try{
        const r = await fetch(BASE + '/presence/' + userId);
        if(r.status !== 200) return;
        const data = await r.json();
        const el = document.getElementById('my-presence'); if(el) el.textContent = data.status || 'unknown';
        const dot = document.getElementById('my-presence-dot');
        if(dot){ const status = (data.status || '').toLowerCase(); if(status === 'online') dot.style.background = 'green'; else if(status === 'afk') dot.style.background = 'orange'; else dot.style.background = 'gray'; }
      }catch(e){ console.warn('presence poll failed', e); }
    }
    update();
    if(_presenceInterval) clearInterval(_presenceInterval);
    _presenceInterval = setInterval(update, 10000);
  }

  async function closePresence(tabId, token){
    try{ await fetch(BASE + '/presence/close', {method:'POST', headers:{'content-type':'application/json','Authorization':'Bearer ' + token}, body: JSON.stringify({tab_id: tabId})}); }catch(e){}
  }

  try{ window.startHeartbeat = startHeartbeat; window.startPresencePolling = startPresencePolling; window.closePresence = closePresence; window.presence = { startHeartbeat, startPresencePolling, closePresence }; }catch(e){}
})();
