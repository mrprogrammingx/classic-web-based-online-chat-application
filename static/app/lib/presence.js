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
      // Issue a single initial heartbeat to register this tab.
      // Subsequent heartbeats are driven exclusively by user activity
      // (startActivityMonitoring) so last_active naturally goes stale
      // after ~60 s of inactivity, which the server interprets as AFK.
      const p = heartbeat();
      // Always await the initial heartbeat to ensure tab_presence is registered
      // before presence polling queries the server
      try{ await p; }catch(e){}
      if(window._hb) try{ clearInterval(window._hb); window._hb = null; }catch(e){}
      // NOTE: no setInterval here — activity monitoring handles ongoing heartbeats
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
          // Update dot class to match status (CSS will handle the color)
          if(dot){
            const statusClass = String(display).toLowerCase();
            dot.className = 'presence-dot ' + statusClass;
          }
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
