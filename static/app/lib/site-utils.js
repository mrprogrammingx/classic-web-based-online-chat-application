// Site-wide utilities (extracted from main.js)
(function(){
  const BASE = location.origin;

  function parseJwt(token){ try{ return JSON.parse(atob(token.split('.')[1])); }catch(e){ return {}; } }

  function siteHref(key, fallback){ try{ if(window && window.SITE_CONFIG && window.SITE_CONFIG[key]) return window.SITE_CONFIG[key]; }catch(e){} return fallback; }

  function showStatus(txt, visible=true, timeout=4000){ const el = document.getElementById('status'); if(!el) return; el.style.display = visible ? 'block' : 'none'; el.textContent = txt; if(visible && timeout>0){ setTimeout(()=>{ el.style.display='none' }, timeout) } }

  function authHeaders(contentType){ const h = {}; if(contentType) h['Content-Type'] = contentType; try{ if(window && window.appState && window.appState.token) h['Authorization'] = 'Bearer ' + window.appState.token; }catch(e){} return h; }

  // Focus trap helpers
  let _previouslyFocused = null;
  function trapFocus(root){ if(!root) return; _previouslyFocused = document.activeElement; const focusable = root.querySelectorAll('button, [href], input, textarea, [tabindex]:not([tabindex="-1"])'); const first = focusable[0]; const last = focusable[focusable.length-1]; function keyHandler(e){ if(e.key === 'Tab'){ if(e.shiftKey){ if(document.activeElement === first){ e.preventDefault(); last.focus(); } } else { if(document.activeElement === last){ e.preventDefault(); first.focus(); } } } else if(e.key === 'Escape'){ root.style.display='none'; releaseFocusTrap(); } } root.__focusHandler = keyHandler; document.addEventListener('keydown', keyHandler); if(first) setTimeout(()=> first.focus(), 0); }
  function releaseFocusTrap(){ try{ if(_previouslyFocused && _previouslyFocused.focus) _previouslyFocused.focus(); }catch(e){} if(document && document.__focusHandler) document.removeEventListener('keydown', document.__focusHandler); }

  function ensureUiRoots(){ try{ if(!document.getElementById('modal-root')){ const m = document.createElement('div'); m.id = 'modal-root'; document.body.appendChild(m); } if(!document.getElementById('toast-root')){ const t = document.createElement('div'); t.id = 'toast-root'; document.body.appendChild(t); } }catch(e){}
  }

  try{ window.parseJwt = parseJwt; window.siteHref = siteHref; window.showStatus = showStatus; window.authHeaders = authHeaders; window.trapFocus = trapFocus; window.releaseFocusTrap = releaseFocusTrap; window.ensureUiRoots = ensureUiRoots; window.appState = window.appState || {}; window.appState.tabId = window.appState.tabId || ('tab-' + Math.random().toString(36).slice(2,9)); }catch(e){}
})();
