// Convenience loader: include this file on pages that want all app libs in one script
(function(){
  // Map a script src to a small predicate that returns true when the runtime
  // already provides the same functionality. This avoids injecting duplicate
  // implementations (which previously caused recursion/errors).
  const libMap = [
    { src: '/static/app/lib/site-utils.js', skip: ()=> !!(window && (window.parseJwt || window.siteHref || window.ensureUiRoots)) },
    { src: '/static/app/lib/auth.js', skip: ()=> !!(window && window.initAuthUi) },
    { src: '/static/app/lib/auth-pages.js', skip: ()=> !!(window && (window.register || window.login || window.initAuthPages)) },
  // don't skip sessions.js just because a minimal renderUserInfo exists
  { src: '/static/app/lib/sessions.js', skip: ()=> !!(window && (window.loadSessions || window.initSessionsUi)) },
  // Only skip injecting presence.js when the canonical `window.presence` object
  // is already present. Some pages (main.js) define lightweight helpers like
  // startHeartbeat which are not full implementations; we prefer the lib
  // implementation when available.
  { src: '/static/app/lib/presence.js', skip: ()=> !!(window && window.presence) },
    { src: '/static/app/lib/friends.js', skip: ()=> !!(window && (window.loadFriends || window.loadIncomingRequests)) },
    { src: '/static/app/lib/admin.js', skip: ()=> !!(window && window.openAdmin) },
    { src: '/static/app/lib/composer.js', skip: ()=> !!(window && window.handleComposerSubmit) }
  ];

  function scriptAlreadyPresent(src){
    return Array.from(document.scripts).some(s => s.src && s.src.indexOf(src) !== -1);
  }

  for(const entry of libMap){
    try{
      if(entry.skip && entry.skip()) continue;
      if(scriptAlreadyPresent(entry.src)) continue;
      const s = document.createElement('script'); s.src = entry.src; s.async = false; document.head.appendChild(s);
    }catch(e){}
  }
})();
