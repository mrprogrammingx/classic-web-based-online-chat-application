const BASE = location.origin;
let token = null;
let jti = null;
let tabId = 'tab-' + Math.random().toString(36).slice(2,9);
const page = location.pathname;

// Ensure UI roots exist (modal + toast) so pages like login/register that don't include
// the modal/toast containers still get the async modal/toast UX.
function ensureUiRoots(){
  try{
    if(window && typeof window.ensureUiRoots === 'function' && window.ensureUiRoots !== ensureUiRoots){
      return window.ensureUiRoots();
    }
  }catch(e){}
  try{
    if(!document.getElementById('modal-root')){
      const m = document.createElement('div'); m.id = 'modal-root'; document.body.appendChild(m);
    }
    if(!document.getElementById('toast-root')){
      const t = document.createElement('div'); t.id = 'toast-root'; document.body.appendChild(t);
    }
  }catch(e){}
}
if(document.readyState === 'loading') window.addEventListener('DOMContentLoaded', ensureUiRoots); else ensureUiRoots();

// Autofocus email input on simple auth pages and submit on Enter
function setupAuthPageHelpers(){
  try{
    if(window && typeof window.initAuthPages === 'function'){
      return window.initAuthPages();
    }
  }catch(e){}
  try{
    const email = document.getElementById('email');
    function renderUserInfo(user){
      try{ if(window && typeof window.renderUserInfo === 'function' && window.renderUserInfo !== renderUserInfo) return window.renderUserInfo(user); }catch(e){}
      // Minimal fallback: do nothing — pages that need a full UI should include sessions.js
    }
  }catch(e){}
}
// Note: synchronous confirm fallback removed. Use async showModal(opts) instead.
function showToast(msg, type='error', timeout=4000){
  try{ if(window && typeof window.showToast === 'function') return window.showToast(msg, type, timeout); }catch(e){}
  // Lazy-load UI lib (best-effort) and fallback to console
  try{ if(!(window && typeof window.showToast === 'function')){ const s = document.createElement('script'); s.src = '/static/app/ui/ui.js'; s.async = true; document.head.appendChild(s); } }catch(e){}
  console.warn('toast fallback:', msg);
}

// showAlert returns a Promise resolved when the dialog is dismissed
function showAlert(body, title){
  try{ if(window && typeof window.showModal === 'function') return window.showModal({ title: title || '', body: body || '', confirmText: t('ok') }); }catch(e){}
  return new Promise((resolve)=>{
    try{
      if(!(window && typeof window.showModal === 'function')){
        const s = document.createElement('script'); s.src = '/static/app/ui/ui.js';
        s.onload = ()=>{ try{ if(window && typeof window.showModal === 'function') { const okText = (typeof t === 'function') ? t('ok') : 'OK'; window.showModal({ title: title || '', body: body || '', confirmText: okText }).then(resolve).catch(()=>resolve()); } else resolve(); }catch(e){ resolve(); } };
        s.onerror = ()=> resolve();
        document.head.appendChild(s);
      } else { try{ const okText = (typeof t === 'function') ? t('ok') : 'OK'; window.showModal({ title: title || '', body: body || '', confirmText: okText }).then(resolve).catch(()=>resolve()); }catch(e){ resolve(); } }
    }catch(e){ resolve(); }
  });
}

// try to bootstrap from HttpOnly cookie on page load (only on home)
async function init(){
  try{
    const r = await fetch(BASE + '/refresh', {method: 'POST', credentials: 'include'});
    if(r.status === 200){
      const data = await r.json();
      // server may return token and user
      if(data.token){
        token = data.token;
        jti = token && parseJwt(token).jti;
      }
      if(data.user){
        await afterAuth(data.user);
      }
    } else {
      // helpful debug: log response body when refresh fails
      try{
        const body = await r.text();
        console.warn('/refresh non-200', r.status, body);
      }catch(e){ console.warn('/refresh non-200 and body parse failed', e) }
    }
  }catch(e){ console.warn('refresh failed', e) }
}

// Render the user-info dropdown (shared across pages)
function renderUserInfo(user){
  try{ if(window && typeof window.renderUserInfo === 'function' && window.renderUserInfo !== renderUserInfo) return window.renderUserInfo(user); }catch(e){}
  // Minimal fallback: create a small user-toggle so pages that don't load sessions.js
  // still show a user name (tests look for '.user-toggle strong'). This is
  // intentionally lightweight; the full sessions lib will upgrade this when
  // available.
  try{
    const ui = document.getElementById('user-info'); if(!ui) return;
    ui.innerHTML = '';
    const dropdown = document.createElement('div'); dropdown.className = 'user-dropdown';
    const toggle = document.createElement('div'); toggle.className = 'user-toggle'; toggle.id = 'user-toggle'; toggle.tabIndex = 0;
    const avatar = document.createElement('span'); avatar.className = 'avatar'; avatar.textContent = String((user.username||user.email||'U').charAt(0)).toUpperCase();
    const strong = document.createElement('strong'); strong.textContent = (user.username || user.email || ('user'+user.id));
    toggle.appendChild(avatar); toggle.appendChild(strong);
    dropdown.appendChild(toggle); ui.appendChild(dropdown);
  }catch(e){}
}
window.addEventListener('load', async ()=>{
  // Only bootstrap on pages that include the header/user-info (we intentionally skip login/register)

// Focus trap helpers for accessibility
// Delegate to extracted implementation if present; otherwise provide a minimal shim.
if(!(window && typeof window.trapFocus === 'function')){
  let _previouslyFocused = null;
  function trapFocus(root){ if(!root) return; _previouslyFocused = document.activeElement; const focusable = root.querySelectorAll('button, [href], input, textarea, [tabindex]:not([tabindex="-1"])'); const first = focusable[0]; const last = focusable[focusable.length-1]; function keyHandler(e){ if(e.key === 'Tab'){ if(e.shiftKey){ if(document.activeElement === first){ e.preventDefault(); last.focus(); } } else { if(document.activeElement === last){ e.preventDefault(); first.focus(); } } } else if(e.key === 'Escape'){ root.style.display='none'; releaseFocusTrap(); } } root.__focusHandler = keyHandler; document.addEventListener('keydown', keyHandler); if(first) setTimeout(()=> first.focus(), 0); }
  function releaseFocusTrap(){ try{ if(_previouslyFocused && _previouslyFocused.focus) _previouslyFocused.focus(); }catch(e){} if(document && document.__focusHandler) document.removeEventListener('keydown', document.__focusHandler); }
  window.trapFocus = trapFocus; window.releaseFocusTrap = releaseFocusTrap;
}
  if(!document.getElementById('user-info')) return;
  // if the login/register just redirected here, bootstrap from sessionStorage first
  try{
    const raw = sessionStorage.getItem('boot_user');
    if(raw){
      const user = JSON.parse(raw);
      await afterAuth(user);
      sessionStorage.removeItem('boot_user');
    }
  }catch(e){ console.warn('boot_user parse failed', e) }
  // also restore token/jti so immediate API calls use them until /refresh runs
  try{
    const bt = sessionStorage.getItem('boot_token');
    const bj = sessionStorage.getItem('boot_jti');
    if(bt){ token = bt; try{ window.appState = window.appState || {}; window.appState.token = token; }catch(e){} }
    if(bj){ jti = bj; }
    sessionStorage.removeItem('boot_token'); sessionStorage.removeItem('boot_jti');
  }catch(e){}
  // now attempt authoritative refresh from cookie (logs on failure)
  await init();
  // bind unread button if present (pages that include main.js should attach this)
  try{ if(typeof attachUnreadHandlers === 'function') attachUnreadHandlers(); }catch(e){}
});

// If header is injected after initial parse, re-run init when it's loaded
window.addEventListener('shared-header-loaded', async ()=>{
  try{ if(document.getElementById('user-info')) await init(); }catch(e){}
  try{
    const adminBtn = document.getElementById('admin-open'); if(adminBtn) adminBtn.onclick = ()=>{ try{ if(window && typeof window.openAdminPanel === 'function') return window.openAdminPanel(); if(window && typeof window.openAdminFallback === 'function') return window.openAdminFallback(); if(window && typeof window.openAdmin === 'function') return window.openAdmin(); return openAdmin(); }catch(e){ return openAdmin(); } };
    const adminCloseBtn = document.getElementById('admin-close'); if(adminCloseBtn) adminCloseBtn.onclick = ()=>{ const m = document.getElementById('admin-modal'); if(m) m.style.display='none' };
  }catch(e){}
  try{ if(typeof attachUnreadHandlers === 'function') attachUnreadHandlers(); }catch(e){}
});

// openUnreadPanel is provided by static/unread.js now; no local copy here

async function register(){
  try{ if(window && typeof window.register === 'function' && window.register !== register) return window.register(); }catch(e){}
  // fallback to original inline implementation
  const emailEl = document.getElementById('email'); const usernameEl = document.getElementById('username'); const passwordEl = document.getElementById('password');
  const email = emailEl ? emailEl.value : '';
  const username = usernameEl ? usernameEl.value : '';
  const password = passwordEl ? passwordEl.value : '';
  const r = await fetch(BASE + '/register', {method:'POST', credentials: 'include', headers:{'content-type':'application/json'}, body: JSON.stringify({email, username, password})});
  const data = await r.json();
  if(r.status===200){
    token = data.token;
    jti = data.token && parseJwt(data.token).jti;
    try{ sessionStorage.setItem('boot_user', JSON.stringify(data.user)); sessionStorage.setItem('boot_token', data.token || ''); const pj = data.token ? JSON.parse(atob(data.token.split('.')[1])) : {}; sessionStorage.setItem('boot_jti', pj.jti || ''); }catch(e){}
    location.href = siteHref('homeHref', '/static/home.html');
  } else {
    try{ await showAlert(JSON.stringify(data), 'Registration failed'); }catch(e){}
  }
}

async function login(){
  try{ if(window && typeof window.login === 'function' && window.login !== login) return window.login(); }catch(e){}
  const emailEl = document.getElementById('email'); const passwordEl = document.getElementById('password');
  const email = emailEl ? emailEl.value : '';
  const password = passwordEl ? passwordEl.value : '';
  const r = await fetch(BASE + '/login', {method:'POST', credentials: 'include', headers:{'content-type':'application/json'}, body: JSON.stringify({email, password})});
  const data = await r.json();
  if(r.status===200){
    token = data.token;
    jti = data.token && parseJwt(data.token).jti;
    try{ sessionStorage.setItem('boot_user', JSON.stringify(data.user)); sessionStorage.setItem('boot_token', data.token || ''); const pj = data.token ? JSON.parse(atob(data.token.split('.')[1])) : {}; sessionStorage.setItem('boot_jti', pj.jti || ''); }catch(e){}
    location.href = siteHref('homeHref', '/static/home.html');
  } else {
    try{ console.log('login failed, calling showAlert with', data); await showAlert(JSON.stringify(data), 'Login failed'); }catch(e){}
  }
}

async function listSessions(){
  try{ if(window && typeof window.loadSessions === 'function') return window.loadSessions(); }catch(e){}
  // If the sessions lib isn't present, attempt to dynamically load it (non-blocking)
  if(!(window && typeof window.loadSessions === 'function')){
    const s = document.createElement('script'); s.src = '/static/app/lib/sessions.js'; s.async = true; document.head.appendChild(s);
    // give the script a moment to load and then call the delegating function again
    setTimeout(()=>{ try{ if(window && typeof window.loadSessions === 'function') window.loadSessions(); }catch(e){} }, 100);
  }
}

function parseJwt (token) {
  try{ if(window && typeof window.parseJwt === 'function' && window.parseJwt !== parseJwt) return window.parseJwt(token); }catch(e){}
  try{ return JSON.parse(atob(token.split('.')[1])); }catch(e){return {}};
}

// helper to read canonical site hrefs exposed by header-loader (falls back to provided default)
function siteHref(key, fallback){
  try{ if(window && typeof window.siteHref === 'function') return window.siteHref(key, fallback); }catch(e){}
  try{ if(window && window.SITE_CONFIG && window.SITE_CONFIG[key]) return window.SITE_CONFIG[key]; }catch(e){}
  return fallback;
}

function authHeaders(contentType){
  try{ if(window && typeof window.authHeaders === 'function' && window.authHeaders !== authHeaders) return window.authHeaders(contentType); }catch(e){}
  const h = {};
  if(contentType) h['Content-Type'] = contentType;
  try{ if(window && window.appState && window.appState.token) h['Authorization'] = 'Bearer ' + window.appState.token; }catch(e){}
  return h;
}

function showStatus(txt, visible=true, timeout=4000){
  try{ if(window && typeof window.showStatus === 'function') return window.showStatus(txt, visible, timeout); }catch(e){}
  const el = document.getElementById('status');
  if(!el) return;
  el.style.display = visible ? 'block' : 'none';
  el.textContent = txt;
  if(visible && timeout>0){ setTimeout(()=>{ el.style.display='none' }, timeout) }
}

function onLogin(user){
  try{ if(window && typeof window.onLogin === 'function') return window.onLogin(user); }catch(e){}
  try{
    const meEl = document.getElementById('me');
    if(meEl){ meEl.style.display='block'; const nameEl = document.getElementById('me-name'); if(nameEl) nameEl.textContent = user.username; }
  }catch(e){}
  try{ if(window && typeof window.startHeartbeat === 'function' && window.startHeartbeat !== startHeartbeat) window.startHeartbeat(); else startHeartbeat(); }catch(e){}
  try{ if(window && typeof window.startPresencePolling === 'function' && window.startPresencePolling !== startPresencePolling) window.startPresencePolling(user.id); else startPresencePolling(user.id); }catch(e){}
}

async function fetchMeAndMaybeShowAdmin(){
  try{ if(window && typeof window.fetchMeAndMaybeShowAdmin === 'function' && window.fetchMeAndMaybeShowAdmin !== fetchMeAndMaybeShowAdmin) return window.fetchMeAndMaybeShowAdmin(); }catch(e){}
  try{
    const r = await fetch(BASE + '/me', {headers:{'Authorization':'Bearer ' + token}});
    if(r.status !== 200) return;
    const data = await r.json();
    const u = data.user;
    try{ const el = document.getElementById('admin-open'); if(el) el.style.display = (u && u.is_admin) ? 'inline' : 'none'; }catch(e){}
  }catch(e){ console.warn('failed to fetch /me', e) }
}

async function heartbeat(){
  try{ if(window && typeof window.heartbeat === 'function' && window.heartbeat !== heartbeat) return window.heartbeat(); }catch(e){}
  if(!token || !jti) return;
  try{ await fetch(BASE + '/presence/heartbeat', {method:'POST', headers:{'content-type':'application/json','Authorization':'Bearer ' + token}, body: JSON.stringify({tab_id: tabId, jti})}); }catch(e){}
}

function startHeartbeat(){
  try{ if(window && typeof window.startHeartbeat === 'function' && window.startHeartbeat !== startHeartbeat) return window.startHeartbeat(); }catch(e){}
  heartbeat(); window._hb = setInterval(heartbeat, 20000);
}

let _presenceInterval = null;
function startPresencePolling(userId){
  try{ if(window && typeof window.startPresencePolling === 'function' && window.startPresencePolling !== startPresencePolling) return window.startPresencePolling(userId); }catch(e){}
  // local fallback: poll presence every 10s
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
  update(); if(_presenceInterval) clearInterval(_presenceInterval); _presenceInterval = setInterval(update, 10000);
}

// after login/register, fetch authoritative /me to decide admin visibility
async function afterAuth(user){
  onLogin(user);
  // server now returns is_admin on login/register/refresh; use it for immediate UI
  const adminBtn = document.getElementById('admin-open');
  if(adminBtn){
    adminBtn.style.display = (user && user.is_admin) ? 'inline' : 'none';
  }
  // render shared header user info
  try{ renderUserInfo(user); }catch(e){}
  // still refresh authoritative data in background
  fetchMeAndMaybeShowAdmin();
  // load friends and incoming requests so UI is populated
  try{ loadFriends(); }catch(e){}
  try{ loadIncomingRequests(); }catch(e){}
}

window.addEventListener('beforeunload', async ()=>{
  try{ if(window && typeof window.closePresence === 'function') { await window.closePresence(tabId, token); } else { await fetch(BASE + '/presence/close', {method:'POST', headers:{'content-type':'application/json','Authorization':'Bearer ' + token}, body: JSON.stringify({tab_id: tabId})}); } }catch(e){}
});

const regBtn = document.getElementById('register'); if(regBtn) regBtn.onclick = register;
const loginBtn = document.getElementById('login'); if(loginBtn) loginBtn.onclick = login;
const listBtn = document.getElementById('list-sessions'); if(listBtn) listBtn.onclick = listSessions;
const addFriendBtn = document.getElementById('add-friend'); if(addFriendBtn) addFriendBtn.onclick = async ()=>{
  const fid = parseInt(document.getElementById('friend-id-input').value || '0');
  if(!fid) return showToast('enter numeric friend id', 'error');
  try{
  addFriendBtn.disabled = true;
  showStatus('Sending friend add...');
  console.log('POST /friends/add', { friend_id: fid });
  const r = await fetch(BASE + '/friends/add', {method:'POST', credentials: 'include', headers: authHeaders('application/json'), body: JSON.stringify({friend_id: fid})});
  console.log('/friends/add response', r.status, await r.clone().text());
  if(r.status===200) await loadFriends(); else { const body = await r.json().catch(()=>null); showStatus('Failed: ' + JSON.stringify(body)); showToast(JSON.stringify(body), 'error'); }
  }catch(e){ showToast('failed to add friend', 'error') }
  finally{ addFriendBtn.disabled = false }
}

const requestByUsernameBtn = document.getElementById('request-by-username'); if(requestByUsernameBtn) requestByUsernameBtn.onclick = async ()=>{
  const uname = document.getElementById('friend-username-input').value || '';
  if(!uname) return showToast('enter username', 'error');
  try{
  requestByUsernameBtn.disabled = true;
  showStatus('Sending friend request...');
  console.log('POST /friends/request', { username: uname });
  const r = await fetch(BASE + '/friends/request', {method:'POST', credentials: 'include', headers: authHeaders('application/json'), body: JSON.stringify({username: uname, message: 'hi'})});
  console.log('/friends/request response', r.status, await r.clone().text());
  if(r.status === 200){ await loadIncomingRequests(); await loadFriends(); showStatus('Request sent'); showToast('request sent', 'success') } else { const body = await r.json().catch(()=>null); showStatus('Failed: ' + JSON.stringify(body)); showToast(JSON.stringify(body), 'error') }
  }catch(e){ showToast('failed to send request', 'error') }
  finally{ requestByUsernameBtn.disabled = false }
}

const logoutBtn = document.getElementById('logout'); if(logoutBtn) logoutBtn.onclick = async ()=>{
  await fetch(BASE + '/logout', {method:'POST', headers:{'Authorization':'Bearer ' + token}, credentials: 'include'});
  token = null; jti = null; location.href = '/static/auth/login.html';
}

const debugBtn = document.getElementById('debug-inspect'); if(debugBtn) debugBtn.onclick = async ()=>{
  try{
    showStatus('Inspecting...');
    const r = await fetch(BASE + '/debug/inspect', {credentials: 'include'});
    const data = await r.json();
    console.log('/debug/inspect', data);
    showStatus(JSON.stringify(data), true, 10000);
  }catch(e){ console.warn('debug inspect failed', e); showStatus('inspect failed'); }
}

// admin UI
async function openAdmin(){
  try{ if(window && typeof window.openAdminPanel === 'function') return window.openAdminPanel(); }catch(e){}
  try{ if(window && typeof window.openAdmin === 'function' && window.openAdmin !== openAdmin) return window.openAdmin(); }catch(e){}
  // lazy-load admin lib if present
  if(!(window && typeof window.openAdmin === 'function')){
    const s = document.createElement('script'); s.src = '/static/app/lib/admin.js'; s.async = true; document.head.appendChild(s);
    setTimeout(()=>{ try{ if(window && typeof window.openAdmin === 'function') window.openAdmin(); }catch(e){} }, 100);
  }
}
const adminOpenBtn = document.getElementById('admin-open'); if(adminOpenBtn) adminOpenBtn.onclick = openAdmin;
const adminCloseBtn = document.getElementById('admin-close'); if(adminCloseBtn) adminCloseBtn.onclick = ()=>{ const m = document.getElementById('admin-modal'); if(m) m.style.display='none' }

async function loadFriends(){
  try{ if(window && typeof window.loadFriends === 'function' && window.loadFriends !== loadFriends) return window.loadFriends(); }catch(e){}
  // lazy-load friends lib if not present
  if(!(window && typeof window.loadFriends === 'function')){
    const s = document.createElement('script'); s.src = '/static/app/lib/friends.js'; s.async = true; document.head.appendChild(s);
    setTimeout(()=>{ try{ if(window && typeof window.loadFriends === 'function') window.loadFriends(); }catch(e){} }, 100);
  }
}

async function loadIncomingRequests(){
  try{ if(window && typeof window.loadIncomingRequests === 'function' && window.loadIncomingRequests !== loadIncomingRequests) return window.loadIncomingRequests(); }catch(e){}
  if(!(window && typeof window.loadIncomingRequests === 'function')){
    const s = document.createElement('script'); s.src = '/static/app/lib/friends.js'; s.async = true; document.head.appendChild(s);
    setTimeout(()=>{ try{ if(window && typeof window.loadIncomingRequests === 'function') window.loadIncomingRequests(); }catch(e){} }, 100);
  }
}

// ensure incoming requests refresher
setInterval(()=>{ if(token) loadIncomingRequests() }, 15000);

// show admin button for admins (quick heuristic: fetch sessions and check for is_admin via /sessions is not sufficient; we show button and the server will enforce admin rights)
function maybeShowAdmin(){
  // kept for backward compatibility; prefer /me for authoritative info
  // no-op now; visibility controlled by fetchMeAndMaybeShowAdmin
}

