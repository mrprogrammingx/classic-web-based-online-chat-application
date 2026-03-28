// Deprecated shim: use /static/app/lib/presence.js instead. This file delegates
// to the canonical library implementation to avoid duplicate implementations.
(function(){
  try{
    console.info('data/presence.js shim loaded; delegating to lib/presence.js');
    // If lib/presence.js provides a presence API, expose the same window symbols.
    if(window && window.presence){
      window.startHeartbeat = window.startHeartbeat || window.presence.startHeartbeat;
      window.startPresencePolling = window.startPresencePolling || window.presence.startPresencePolling;
      window.closePresence = window.closePresence || window.presence.closePresence;
      window.startActivityMonitoring = window.startActivityMonitoring || window.presence.startActivityMonitoring;
    }
  }catch(e){ console.warn('presence shim failed', e); }
})();
