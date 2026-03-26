const BASE = location.origin;
let token = null;
let jti = null;
let tabId = 'tab-' + Math.random().toString(36).slice(2,9);
const page = location.pathname;

// Ensure UI roots exist (modal + toast) so pages like login/register that don't include
// the modal/toast containers still get the async modal/toast UX.
function ensureUiRoots(){
  try{
    if(window && typeof window.ensureUiRoots === 'function'){
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
    if(email) email.focus();
    // allow Enter to trigger the primary button if present
    document.addEventListener('keydown', (e)=>{
      if(e.key === 'Enter'){
        const active = document.activeElement;
        // ignore Enter when inside a textarea
        if(active && active.tagName && active.tagName.toLowerCase() === 'textarea') return;
        const login = document.getElementById('login');
        const reg = document.getElementById('register');
        if(login && document.getElementById('email')) { login.click(); }
        else if(reg && document.getElementById('username')) { reg.click(); }
      }
    });
    // bind click handlers for login/register buttons when present so pages relying
    // only on main.js still work without an extra auth script
    try{
      const loginBtn = document.getElementById('login');
      if(loginBtn && !loginBtn.__boundToLogin){ loginBtn.addEventListener('click', ()=>{ try{ login(); }catch(e){} }); loginBtn.__boundToLogin = true; }
      const regBtn = document.getElementById('register');
      if(regBtn && !regBtn.__boundToRegister){ regBtn.addEventListener('click', ()=>{ try{ register(); }catch(e){} }); regBtn.__boundToRegister = true; }
    }catch(e){}
  }catch(e){}
}
if(document.readyState === 'loading') window.addEventListener('DOMContentLoaded', setupAuthPageHelpers); else setupAuthPageHelpers();

// small HTML-escape helper for safe modal bodies
function escapeHtml(str){
  return String(str).replace(/[&<>'"]/g, (s)=>({ '&':'&amp;', '<':'&lt;', '>':'&gt;', "'":"&#39;", '"':'&quot;' }[s]));
}

// Minimal i18n helper
const _STRINGS = { en: { ok: 'OK', cancel: 'Cancel', ban: 'Ban', keep: 'Keep', revoke: 'Revoke' } };
function t(key, lang='en'){ return (_STRINGS[lang] && _STRINGS[lang][key]) || _STRINGS.en[key] || key; }

// Polished modal alert for pages that only load main.js (login/register).
// Returns a Promise resolved when user dismisses the dialog.
function showAlert(body, title){
  try{ if(window && typeof window.showModal === 'function'){ console.log('showAlert delegating to window.showModal', title); return window.showModal({ title: title || '', body: body || '', confirmText: t('ok') }); } }catch(e){}
  return new Promise((resolve)=>{
    console.log('showAlert building fallback modal', title, body && (typeof body === 'string' ? body.slice(0,200) : 'non-string'));
    let root = document.getElementById('modal-root');
    if(!root){ try{ root = document.createElement('div'); root.id = 'modal-root'; document.body.appendChild(root); }catch(e){} }
    if(!root) { alert(body); resolve(); return; }
    root.innerHTML = '';
    const previouslyFocused = document.activeElement;
    const backdrop = document.createElement('div'); backdrop.className = 'modal-backdrop';
    const box = document.createElement('div'); box.className = 'modal-box';
    const titleEl = document.createElement('h3'); const titleId = 'modal-title-' + Math.random().toString(36).slice(2,9);
    titleEl.id = titleId; titleEl.textContent = title || '';
  const bodyEl = document.createElement('div'); bodyEl.className = 'modal-body'; bodyEl.innerHTML = `${escapeHtml(body || '')}`;
    const actions = document.createElement('div'); actions.className = 'modal-actions';
  const ok = document.createElement('button'); ok.type='button'; ok.textContent = t('ok'); ok.className='confirm';
    actions.appendChild(ok);
    box.appendChild(titleEl); box.appendChild(bodyEl); box.appendChild(actions);
    box.setAttribute('role','dialog'); box.setAttribute('aria-modal','true'); box.setAttribute('aria-labelledby', titleId);
    backdrop.appendChild(box); root.appendChild(backdrop);

    function cleanup(){ root.innerHTML = ''; document.removeEventListener('keydown', onKey); try{ if(previouslyFocused && previouslyFocused.focus) previouslyFocused.focus(); }catch(e){} }
    function onKey(e){ if(e.key === 'Escape'){ cleanup(); resolve(); } else if(e.key === 'Tab'){ e.preventDefault(); ok.focus(); } }
    ok.addEventListener('click', ()=>{ cleanup(); resolve(); });
    backdrop.addEventListener('click', (e)=>{ if(e.target === backdrop){ cleanup(); resolve(); } });
    document.addEventListener('keydown', onKey);
    setTimeout(()=>{ try{ ok.focus(); }catch(e){} }, 0);
  });
}

// Modal & toast utilities (use DOM roots if present, fall back to native dialogs)
// Note: synchronous confirm fallback removed. Use async showModal(opts) instead.
function showToast(msg, type='error', timeout=4000){
  try{ if(window && typeof window.showToast === 'function') return window.showToast(msg, type, timeout); }catch(e){}
  let root = document.getElementById('toast-root');
  // if the page didn't include a toast root, create a temporary one so we don't rely on window.alert
  if(!root){
    try{
      root = document.createElement('div');
      root.id = 'toast-root';
      document.body.appendChild(root);
    }catch(e){
      // last-resort fallback to console if DOM not available
      console.warn('toast fallback:', msg);
      return;
    }
  }
  if(!root.querySelector('.toast-container')){
    const cont=document.createElement('div'); cont.className='toast-container';
    cont.setAttribute('role', 'status');
    cont.setAttribute('aria-live', 'polite');
    cont.setAttribute('aria-atomic', 'false');
    root.appendChild(cont);
  }
  const cont = root.querySelector('.toast-container'); const t = document.createElement('div'); t.className = 'toast ' + (type==='success'? 'success': (type==='error'? 'error':'')); t.textContent = msg; t.setAttribute('role','status'); cont.appendChild(t);
  setTimeout(()=>{ t.style.opacity='0'; t.style.transform='translateY(8px)'; setTimeout(()=>t.remove(),240); }, timeout);
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
  try{
    const ui = document.getElementById('user-info'); if(!ui) return;
    const display = escapeHtml(user.username || user.email || ('user'+user.id));
    ui.innerHTML = `
      <div class="user-dropdown">
        <div class="user-toggle" id="user-toggle" tabindex="0">
          <span class="avatar">${escapeHtml((user.username||user.email||'U').charAt(0).toUpperCase())}</span>
          <strong>${display}</strong>
          ${user.is_admin? '<span class="badge">admin</span>':''}
        </div>
        <div class="dropdown-panel" id="user-panel" style="display:none">
          <h4>Sessions</h4>
          <ul class="sessions-list" id="sessions-list"><li class="meta">Loading…</li></ul>
          <div style="margin-top:8px;display:flex;gap:8px;justify-content:space-between">
            <button id="btn-logout-inline" type="button">Logout</button>
            <button id="btn-refresh-sessions" type="button">Refresh</button>
          </div>
        </div>
      </div>
    `;

    const toggle = document.getElementById('user-toggle');
    const panel = document.getElementById('user-panel');
    const sessionsList = document.getElementById('sessions-list');
    const refreshBtn = document.getElementById('btn-refresh-sessions');
    const inlineLogout = document.getElementById('btn-logout-inline');

    // lazy-load sessions only when the panel opens
    let sessionsLoaded = false;

    async function loadSessions(){
      if(!sessionsList) return;
      sessionsList.innerHTML = '<li class="meta">Loading…</li>';
      try{
        const data = await fetch(BASE + '/sessions', {credentials: 'include'}).then(r=>r.json());
        if(!data || !data.sessions) return sessionsList.innerHTML = '<li class="meta">No sessions</li>';
        sessionsList.innerHTML='';
        data.sessions.forEach(s=>{
          const li=document.createElement('li');
          const meta=document.createElement('div'); meta.className='meta';
          meta.textContent = `jti: ${s.jti} • last active: ${new Date((s.last_active||s.created_at||0)*1000).toLocaleString()}`;
          const btn=document.createElement('button'); btn.type='button'; btn.textContent='Revoke';
          btn.addEventListener('click', async ()=>{
            const ok = await showAlert('Revoke this session?','Revoke session'); if(!ok) return;
            try{ btn.disabled=true; const r = await fetch('/sessions/revoke', {method:'POST', credentials:'include', headers:{'Content-Type':'application/json'}, body: JSON.stringify({jti: s.jti})});
              if(r && r.ok){ li.style.transition='opacity 220ms'; li.style.opacity='0'; setTimeout(()=>{ li.remove(); showToast('Session revoked','success'); },260); }
              else { btn.disabled=false; showToast('Failed to revoke session','error'); }
            }catch(e){ btn.disabled=false; showToast('Failed to revoke session','error'); }
          });
          li.appendChild(meta); li.appendChild(btn); sessionsList.appendChild(li);
        });
      }catch(e){ sessionsList.innerHTML = '<li class="meta">Error loading sessions</li>'; }
    }

    function openPanel(){ if(panel) panel.style.display='block'; }
    function closePanel(){ if(panel) panel.style.display='none'; }

    if(toggle) toggle.addEventListener('click', async ()=>{ if(panel && panel.style.display==='block') { closePanel(); releaseFocusTrap(); } else { openPanel(); if(!sessionsLoaded){ await loadSessions(); sessionsLoaded = true; } trapFocus(panel); } });
    if(refreshBtn) refreshBtn.addEventListener('click', ()=> loadSessions());
  if(inlineLogout) inlineLogout.addEventListener('click', async ()=>{ try{ await fetch('/logout', {method:'POST', credentials:'include'}); }catch(e){} location.href='/static/auth/login.html'; });

    // Ensure admin-open is hidden for non-admins (double safety: server enforces admin endpoints)
    try{ const adminBtn = document.getElementById('admin-open'); if(adminBtn && !user.is_admin) adminBtn.style.display = 'none'; }catch(e){}

  }catch(e){ console.warn('renderUserInfo failed', e); }
}
window.addEventListener('load', async ()=>{
  // Only bootstrap on pages that include the header/user-info (we intentionally skip login/register)

// Focus trap helpers for accessibility
let _previouslyFocused = null;
function trapFocus(root){
  if(!root) return;
  _previouslyFocused = document.activeElement;
  const focusable = root.querySelectorAll('button, [href], input, textarea, [tabindex]:not([tabindex="-1"])');
  const first = focusable[0]; const last = focusable[focusable.length-1];
  function keyHandler(e){ if(e.key === 'Tab'){ if(e.shiftKey){ if(document.activeElement === first){ e.preventDefault(); last.focus(); } } else { if(document.activeElement === last){ e.preventDefault(); first.focus(); } } } else if(e.key === 'Escape'){ root.style.display='none'; releaseFocusTrap(); } }
  root.__focusHandler = keyHandler;
  document.addEventListener('keydown', keyHandler);
  if(first) setTimeout(()=> first.focus(), 0);
}
function releaseFocusTrap(){ try{ if(_previouslyFocused && _previouslyFocused.focus) _previouslyFocused.focus(); }catch(e){} if(document && document.__focusHandler) document.removeEventListener('keydown', document.__focusHandler); }
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
  try{
    // use shared handler from static/unread.js if available
    try{ if(typeof attachUnreadHandlers === 'function') attachUnreadHandlers(); }catch(e){}
  }catch(e){}
});

// If header is injected after initial parse, re-run init when it's loaded
window.addEventListener('shared-header-loaded', async ()=>{
  try{ if(document.getElementById('user-info')) await init(); }catch(e){}
  try{
    const adminBtn = document.getElementById('admin-open'); if(adminBtn) adminBtn.onclick = ()=>{ try{ if(window && typeof window.openAdminPanel === 'function') return window.openAdminPanel(); if(window && typeof window.openAdminFallback === 'function') return window.openAdminFallback(); return openAdmin(); }catch(e){ return openAdmin(); } };
    const adminCloseBtn = document.getElementById('admin-close'); if(adminCloseBtn) adminCloseBtn.onclick = ()=>{ const m = document.getElementById('admin-modal'); if(m) m.style.display='none' };
  }catch(e){}
  // ensure unread handler is bound for headers injected after initial load
  try{ if(typeof attachUnreadHandlers === 'function') attachUnreadHandlers(); }catch(e){}
});

// openUnreadPanel is provided by static/unread.js now; no local copy here

async function register(){
  try{ if(window && typeof window.register === 'function') return window.register(); }catch(e){}
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
  try{ if(window && typeof window.login === 'function') return window.login(); }catch(e){}
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
  const r = await fetch(BASE + '/sessions', {headers:{'Authorization': 'Bearer ' + token}});
  const data = await r.json();
  const ul = document.getElementById('sessions'); if(!ul) return;
  ul.innerHTML = '';
  for(const s of data.sessions){
    const li = document.createElement('li');
    li.textContent = `${s.jti} - ${s.ip || 'unknown'} - ${s.user_agent || 'ua'} - last_active:${new Date(s.last_active*1000).toLocaleTimeString()}`;
    const btn = document.createElement('button');
    btn.textContent = 'Revoke';
    btn.onclick = async ()=>{
      await fetch(BASE + '/sessions/revoke', {method:'POST', headers:{'content-type':'application/json','Authorization':'Bearer ' + token}, body: JSON.stringify({jti: s.jti})});
      listSessions();
    }
    li.appendChild(btn);
    ul.appendChild(li);
  }
}

function parseJwt (token) {
  try{ if(window && typeof window.parseJwt === 'function' && window.parseJwt !== parseJwt) return window.parseJwt(token); }catch(e){}
  try{
    return JSON.parse(atob(token.split('.')[1]));
  }catch(e){return {}};
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
  if(token) h['Authorization'] = 'Bearer ' + token;
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
  if(!token || !jti) return;
  await fetch(BASE + '/presence/heartbeat', {method:'POST', headers:{'content-type':'application/json','Authorization':'Bearer ' + token}, body: JSON.stringify({tab_id: tabId, jti})});
}

function startHeartbeat(){
  heartbeat();
  window._hb = setInterval(heartbeat, 20000);
}

let _presenceInterval = null;
function startPresencePolling(userId){
  try{ if(window && typeof window.startPresencePolling === 'function') return window.startPresencePolling(userId); }catch(e){}
  // update presence immediately and then every 10s (local fallback)
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
  // prefer the shared admin UI if available
  if(typeof window.openAdminPanel === 'function'){ return window.openAdminPanel(); }
  try{
    const r = await fetch(BASE + '/admin/users', {headers:{'Authorization':'Bearer ' + token}});
    if(r.status === 403){ showToast('admin required', 'error'); return }
    const data = await r.json();
    const ul = document.getElementById('admin-users'); if(!ul) return;
    ul.innerHTML = '';
    for(const u of data.users){
      const li = document.createElement('li');
      li.textContent = `${u.id} - ${u.email} - ${u.username} - admin:${u.is_admin}`;
      const btn = document.createElement('button'); btn.textContent = 'Delete';
      btn.onclick = async ()=>{ await fetch(BASE + '/admin/users/delete', {method:'POST', headers:{'Content-Type':'application/json','Authorization':'Bearer ' + token}, body: JSON.stringify({id: u.id})}); openAdmin(); }
      li.appendChild(btn); ul.appendChild(li);
    }
    const m = document.getElementById('admin-modal'); if(m) m.style.display = 'block';
  }catch(e){ console.error('openAdmin error', e); }
}
const adminOpenBtn = document.getElementById('admin-open'); if(adminOpenBtn) adminOpenBtn.onclick = openAdmin;
const adminCloseBtn = document.getElementById('admin-close'); if(adminCloseBtn) adminCloseBtn.onclick = ()=>{ const m = document.getElementById('admin-modal'); if(m) m.style.display='none' }

async function loadFriends(){
  try{ if(window && typeof window.loadFriends === 'function' && window.loadFriends !== loadFriends) return window.loadFriends(); }catch(e){}
  try{
    const r = await fetch(BASE + '/friends', {credentials: 'include', headers: authHeaders()});
    if(r.status !== 200) return;
    const data = await r.json();
    const ul = document.getElementById('friends-list'); if(!ul) return;
    ul.innerHTML = '';
    for(const f of data.friends){
      const li = document.createElement('li');
      li.innerHTML = `<span style="display:inline-block;width:10px;height:10px;border-radius:50%;background:gray;margin-right:8px;vertical-align:middle" id="friend-dot-${f.id}"></span> ${f.username} (${f.email}) <button data-id="${f.id}" class="remove-btn">Remove</button> <button data-id="${f.id}" class="ban-btn">Ban</button>`;
      const btn = li.querySelector('.remove-btn'); btn.onclick = async ()=>{ try{ btn.disabled = true; showStatus('Removing friend...'); console.log('POST /friends/remove', { friend_id: f.id }); const r = await fetch(BASE + '/friends/remove', {method:'POST', credentials: 'include', headers: authHeaders('application/json'), body: JSON.stringify({friend_id: f.id})}); console.log('/friends/remove response', r.status, await r.clone().text()); if(r.status===200) await loadFriends(); else { const body = await r.json().catch(()=>null); showStatus('Failed: ' + JSON.stringify(body)); showToast(JSON.stringify(body), 'error'); } }catch(e){ showToast('failed to remove', 'error') } finally{ btn.disabled = false } }
      const banBtn = li.querySelector('.ban-btn'); banBtn.onclick = async ()=>{ try{ const ok = await showModal({title: 'Ban user', body: 'Ban this user? This action cannot be undone.', confirmText: 'Ban', cancelText: 'Keep'}); if(!ok) return; banBtn.disabled = true; showStatus('Sending ban...'); console.log('POST /ban', { banned_id: f.id }); const r = await fetch(BASE + '/ban', {method:'POST', credentials: 'include', headers: authHeaders('application/json'), body: JSON.stringify({banned_id: f.id})}); console.log('/ban response', r.status, await r.clone().text()); if(r.status===200) await loadFriends(); else { const body = await r.json().catch(()=>null); showStatus('Failed: ' + JSON.stringify(body)); showToast(JSON.stringify(body), 'error'); } }catch(e){ showToast('failed to ban', 'error') } finally{ banBtn.disabled = false } }
      ul.appendChild(li);
      // fetch presence for friend and color the dot
      (async (fid)=>{
        try{
          const r2 = await fetch(BASE + '/presence/' + fid);
          if(r2.status !== 200) return;
          const d = await r2.json();
          const dot = document.getElementById('friend-dot-' + fid);
          if(dot){
            const s = (d.status || '').toLowerCase();
            if(s === 'online') dot.style.background = 'green';
            else if(s === 'afk') dot.style.background = 'orange';
            else dot.style.background = 'gray';
          }
        }catch(e){}
      })(f.id);
    }
  }catch(e){console.warn('failed to load friends', e)}
}

async function loadIncomingRequests(){
  try{
    // if an extracted implementation is present and it's not this function, delegate
    if(window && typeof window.loadIncomingRequests === 'function' && window.loadIncomingRequests !== loadIncomingRequests) return window.loadIncomingRequests();
  const r = await fetch(BASE + '/friends/requests', {credentials: 'include', headers: authHeaders()});
    if(r.status !== 200) return;
    const data = await r.json();
    const ul = document.getElementById('incoming-requests'); if(!ul) return;
    ul.innerHTML = '';
    for(const rq of data.requests){
      const li = document.createElement('li');
      li.textContent = `${rq.username} (${rq.email}) - ${rq.message || ''}`;
      const accept = document.createElement('button'); accept.textContent = 'Accept';
  accept.onclick = async ()=>{ try{ accept.disabled = true; showStatus('Accepting...'); console.log('POST /friends/requests/respond', { request_id: rq.id, action: 'accept' }); const r = await fetch(BASE + '/friends/requests/respond', {method:'POST', credentials: 'include', headers: authHeaders('application/json'), body: JSON.stringify({request_id: rq.id, action: 'accept'})}); console.log('/friends/requests/respond response', r.status, await r.clone().text()); if(r.status===200){ await loadIncomingRequests(); await loadFriends(); showStatus('Accepted'); } else { const body = await r.json().catch(()=>null); showStatus('Failed: ' + JSON.stringify(body)); showToast(JSON.stringify(body), 'error'); } }catch(e){ showToast('failed to accept', 'error') } finally{ accept.disabled = false } }
  const reject = document.createElement('button'); reject.textContent = 'Reject';
  reject.onclick = async ()=>{ try{ reject.disabled = true; showStatus('Rejecting...'); console.log('POST /friends/requests/respond', { request_id: rq.id, action: 'reject' }); const r = await fetch(BASE + '/friends/requests/respond', {method:'POST', credentials: 'include', headers: authHeaders('application/json'), body: JSON.stringify({request_id: rq.id, action: 'reject'})}); console.log('/friends/requests/respond response', r.status, await r.clone().text()); if(r.status===200) await loadIncomingRequests(); else { const body = await r.json().catch(()=>null); showStatus('Failed: ' + JSON.stringify(body)); showToast(JSON.stringify(body), 'error'); } }catch(e){ showToast('failed to reject', 'error') } finally{ reject.disabled = false } }
  const ban = document.createElement('button'); ban.textContent = 'Ban';
  ban.onclick = async ()=>{ try{ const ok = await showModal({title: 'Ban user', body: 'Ban this user? This action cannot be undone.', confirmText: 'Ban', cancelText: 'Keep'}); if(!ok) return; ban.disabled = true; showStatus('Sending ban...'); console.log('POST /ban', { banned_id: rq.from_id }); const r = await fetch(BASE + '/ban', {method:'POST', credentials: 'include', headers: authHeaders('application/json'), body: JSON.stringify({banned_id: rq.from_id})}); console.log('/ban response', r.status, await r.clone().text()); if(r.status===200){ await loadIncomingRequests(); await loadFriends(); showStatus('Banned'); } else { const body = await r.json().catch(()=>null); showStatus('Failed: ' + JSON.stringify(body)); showToast(JSON.stringify(body), 'error'); } }catch(e){ showToast('failed to ban', 'error') } finally{ ban.disabled = false } }
      li.appendChild(accept); li.appendChild(reject); li.appendChild(ban);
      ul.appendChild(li);
    }
  }catch(e){ console.warn('failed to load incoming requests', e) }
}

// ensure incoming requests refresher
setInterval(()=>{ if(token) loadIncomingRequests() }, 15000);

// show admin button for admins (quick heuristic: fetch sessions and check for is_admin via /sessions is not sufficient; we show button and the server will enforce admin rights)
function maybeShowAdmin(){
  // kept for backward compatibility; prefer /me for authoritative info
  // no-op now; visibility controlled by fetchMeAndMaybeShowAdmin
}

