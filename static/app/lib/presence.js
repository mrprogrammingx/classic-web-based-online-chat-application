// Presence and heartbeat helpers (extracted from main.js)
(function(){
  const BASE = location.origin;

  function heartbeat(){
    try{
      const token = (window.appState && window.appState.token) || null;
      const jti = (window.appState && window.appState.jti) || null;
      const tabId = (window.appState && window.appState.tabId) || null;
      // return the fetch promise so callers (tests) can await the first heartbeat
      const headers = {'content-type':'application/json'};
      const payload = { tab_id: tabId };
      const opts = { method: 'POST', headers, body: JSON.stringify(payload) };
      if(token && jti){
        headers['Authorization'] = 'Bearer ' + token;
        payload.jti = jti;
        opts.body = JSON.stringify(payload);
      } else {
        // If token/jti aren't available in JS (cookie-based session), send the
        // request with credentials so the server can authenticate via cookie
        opts.credentials = 'include';
      }
      return fetch(BASE + '/presence/heartbeat', opts).catch(()=>{});
    }catch(e){ console.warn('presence.heartbeat failed', e); }
  }
  async function startHeartbeat(tokenArg, jtiArg, tabIdArg){
    try{
      // If caller provided token/jti/tabId (tests pass them), ensure they're applied
      try{ window.appState = window.appState || {}; if(tokenArg) window.appState.token = tokenArg; if(jtiArg) window.appState.jti = jtiArg; if(tabIdArg) window.appState.tabId = tabIdArg; }catch(e){}
  // Heartbeat interval: read from site config or default to 2000ms
  const hbInterval = (window && window.SITE_CONFIG && window.SITE_CONFIG.presencePollMs) ? parseInt(window.SITE_CONFIG.presencePollMs, 10) : 2000;
      // Issue first heartbeat and optionally await it in test mode to avoid racing with presence GET
      const p = heartbeat();
      if(window && window.__TEST_MODE){ try{ await p; }catch(e){} }
      if(window._hb) try{ clearInterval(window._hb); }catch(e){}
      window._hb = setInterval(heartbeat, hbInterval);
    }catch(e){ console.warn('startHeartbeat failed', e); }
  }

  let _presenceInterval = null;
  function startPresencePolling(userId){
    const BASE = location.origin;
    async function update(){
      try{
        const r = await fetch(BASE + '/presence/' + userId);
        if(r.status !== 200) return;
        const data = await r.json();
        const el = document.getElementById('my-presence');
        const dot = document.getElementById('my-presence-dot');
        try{
          const raw = (data && data.status) ? String(data.status).trim() : '';
          let display = '';
          if(/^online$/i.test(raw)) display = 'online';
          else if(/^afk$/i.test(raw)) display = 'AFK';
          else if(/^offline$/i.test(raw)) display = 'offline';
          else display = 'offline';
          if(el) el.textContent = display;
          if(dot){ const s = String(display).toLowerCase(); if(s === 'online') dot.style.background = 'green'; else if(s === 'afk') dot.style.background = 'orange'; else dot.style.background = 'gray'; }
        }catch(e){ console.warn('presence poll render failed', e); }
      }catch(e){ console.warn('presence poll failed', e); }
    }
    update();
    if(_presenceInterval) clearInterval(_presenceInterval);
  // Presence polling interval: read from site config or default to 2000ms
  const pollInterval = (window && window.SITE_CONFIG && window.SITE_CONFIG.presencePollMs) ? parseInt(window.SITE_CONFIG.presencePollMs, 10) : 2000;
  _presenceInterval = setInterval(update, pollInterval);
  }

  async function closePresence(tabId, token){
    try{ await fetch(BASE + '/presence/close', {method:'POST', headers:{'content-type':'application/json','Authorization':'Bearer ' + token}, body: JSON.stringify({tab_id: tabId})}); }catch(e){}
  }

  try{ window.startHeartbeat = startHeartbeat; window.startPresencePolling = startPresencePolling; window.closePresence = closePresence; }catch(e){}
})();
