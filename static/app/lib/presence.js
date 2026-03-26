// Presence and heartbeat helpers (extracted from main.js)
(function(){
  const BASE = location.origin;

  function heartbeat(){
    try{
      const token = (window.appState && window.appState.token) || null;
      const jti = (window.appState && window.appState.jti) || null;
      const tabId = (window.appState && window.appState.tabId) || null;
      if(!token || !jti) return;
      fetch(BASE + '/presence/heartbeat', {method:'POST', headers:{'content-type':'application/json','Authorization':'Bearer ' + token}, body: JSON.stringify({tab_id: tabId, jti})}).catch(()=>{});
    }catch(e){ console.warn('presence.heartbeat failed', e); }
  }

  function startHeartbeat(){
    try{ heartbeat(); window._hb = setInterval(heartbeat, 20000); }catch(e){ console.warn('startHeartbeat failed', e); }
  }

  let _presenceInterval = null;
  function startPresencePolling(userId){
    const BASE = location.origin;
    async function update(){
      try{
        const r = await fetch(BASE + '/presence/' + userId);
        if(r.status !== 200) return;
        const data = await r.json();
        const el = document.getElementById('my-presence'); if(el) el.textContent = data.status || 'unknown';
        const dot = document.getElementById('my-presence-dot');
        if(dot){
          const status = (data.status || '').toLowerCase();
          if(status === 'online') dot.style.background = 'green';
          else if(status === 'afk') dot.style.background = 'orange';
          else dot.style.background = 'gray';
        }
      }catch(e){ console.warn('presence poll failed', e); }
    }
    update();
    if(_presenceInterval) clearInterval(_presenceInterval);
    _presenceInterval = setInterval(update, 10000);
  }

  async function closePresence(tabId, token){
    try{ await fetch(BASE + '/presence/close', {method:'POST', headers:{'content-type':'application/json','Authorization':'Bearer ' + token}, body: JSON.stringify({tab_id: tabId})}); }catch(e){}
  }

  try{ window.startHeartbeat = startHeartbeat; window.startPresencePolling = startPresencePolling; window.closePresence = closePresence; }catch(e){}
})();
