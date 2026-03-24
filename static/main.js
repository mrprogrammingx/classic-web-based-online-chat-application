const BASE = location.origin;
let token = null;
let jti = null;
let tabId = 'tab-' + Math.random().toString(36).slice(2,9);
const page = location.pathname;

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

window.addEventListener('load', async ()=>{
  if(!page.endsWith('/home.html')) return;
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
    if(bt){ token = bt; }
    if(bj){ jti = bj; }
    sessionStorage.removeItem('boot_token'); sessionStorage.removeItem('boot_jti');
  }catch(e){}
  // now attempt authoritative refresh from cookie (logs on failure)
  await init();
});

async function register(){
  const email = document.getElementById('email').value;
  const username = document.getElementById('username').value;
  const password = document.getElementById('password').value;
  const r = await fetch(BASE + '/register', {method:'POST', credentials: 'include', headers:{'content-type':'application/json'}, body: JSON.stringify({email, username, password})});
  const data = await r.json();
  if(r.status===200){
    token = data.token;
    jti = data.token && parseJwt(data.token).jti;
    // store returned user and token so home can bootstrap immediately (in case cookie isn't present yet)
    try{
      sessionStorage.setItem('boot_user', JSON.stringify(data.user));
      sessionStorage.setItem('boot_token', data.token || '');
      const pj = data.token ? JSON.parse(atob(data.token.split('.')[1])) : {};
      sessionStorage.setItem('boot_jti', pj.jti || '');
    }catch(e){}
    // redirect to home which will call /refresh to bootstrap from cookie
    location.href = '/static/home.html';
  } else {
    alert(JSON.stringify(data));
  }
}

async function login(){
  const email = document.getElementById('email').value;
  const password = document.getElementById('password').value;
  const r = await fetch(BASE + '/login', {method:'POST', credentials: 'include', headers:{'content-type':'application/json'}, body: JSON.stringify({email, password})});
  const data = await r.json();
  if(r.status===200){
    token = data.token;
    jti = data.token && parseJwt(data.token).jti;
    try{
      sessionStorage.setItem('boot_user', JSON.stringify(data.user));
      sessionStorage.setItem('boot_token', data.token || '');
      const pj = data.token ? JSON.parse(atob(data.token.split('.')[1])) : {};
      sessionStorage.setItem('boot_jti', pj.jti || '');
    }catch(e){}
    // redirect to home which will call /refresh to bootstrap from cookie
    location.href = '/static/home.html';
  } else {
    alert(JSON.stringify(data));
  }
}

async function listSessions(){
  const r = await fetch(BASE + '/sessions', {headers:{'Authorization': 'Bearer ' + token}});
  const data = await r.json();
  const ul = document.getElementById('sessions');
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
    try{
        return JSON.parse(atob(token.split('.')[1]));
    }catch(e){return {}};
}

function onLogin(user){
  const meEl = document.getElementById('me');
  if(meEl){
    meEl.style.display='block';
    const nameEl = document.getElementById('me-name'); if(nameEl) nameEl.textContent = user.username;
  }
  startHeartbeat();
  // start presence polling for this user
  try{ startPresencePolling(user.id); }catch(e){}
}

async function fetchMeAndMaybeShowAdmin(){
  try{
    const r = await fetch(BASE + '/me', {headers:{'Authorization':'Bearer ' + token}});
    if(r.status !== 200) return;
    const data = await r.json();
    const u = data.user;
    if(u && u.is_admin){
      document.getElementById('admin-open').style.display = 'inline';
    } else {
      document.getElementById('admin-open').style.display = 'none';
    }
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
  // update presence immediately and then every 10s
  async function update(){
    try{
      const r = await fetch(BASE + '/presence/' + userId);
      if(r.status !== 200) return;
      const data = await r.json();
      const el = document.getElementById('my-presence'); if(el) el.textContent = data.status || 'unknown';
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
  // still refresh authoritative data in background
  fetchMeAndMaybeShowAdmin();
}

window.addEventListener('beforeunload', async ()=>{
  try{ await fetch(BASE + '/presence/close', {method:'POST', headers:{'content-type':'application/json','Authorization':'Bearer ' + token}, body: JSON.stringify({tab_id: tabId})}); }catch(e){}
});

const regBtn = document.getElementById('register'); if(regBtn) regBtn.onclick = register;
const loginBtn = document.getElementById('login'); if(loginBtn) loginBtn.onclick = login;
const listBtn = document.getElementById('list-sessions'); if(listBtn) listBtn.onclick = listSessions;

const logoutBtn = document.getElementById('logout'); if(logoutBtn) logoutBtn.onclick = async ()=>{
  await fetch(BASE + '/logout', {method:'POST', headers:{'Authorization':'Bearer ' + token}, credentials: 'include'});
  token = null; jti = null; location.href = '/static/login.html';
}

// admin UI
async function openAdmin(){
  const r = await fetch(BASE + '/admin/users', {headers:{'Authorization':'Bearer ' + token}});
  if(r.status === 403){ alert('admin required'); return }
  const data = await r.json();
  const ul = document.getElementById('admin-users'); ul.innerHTML = '';
  for(const u of data.users){
    const li = document.createElement('li');
    li.textContent = `${u.id} - ${u.email} - ${u.username} - admin:${u.is_admin}`;
    const btn = document.createElement('button'); btn.textContent = 'Delete';
    btn.onclick = async ()=>{ await fetch(BASE + '/admin/users/delete', {method:'POST', headers:{'Content-Type':'application/json','Authorization':'Bearer ' + token}, body: JSON.stringify({id: u.id})}); openAdmin(); }
    li.appendChild(btn); ul.appendChild(li);
  }
  document.getElementById('admin-modal').style.display = 'block';
}
const adminOpenBtn = document.getElementById('admin-open'); if(adminOpenBtn) adminOpenBtn.onclick = openAdmin;
const adminCloseBtn = document.getElementById('admin-close'); if(adminCloseBtn) adminCloseBtn.onclick = ()=>{ const m = document.getElementById('admin-modal'); if(m) m.style.display='none' }

// show admin button for admins (quick heuristic: fetch sessions and check for is_admin via /sessions is not sufficient; we show button and the server will enforce admin rights)
function maybeShowAdmin(){
  // kept for backward compatibility; prefer /me for authoritative info
  // no-op now; visibility controlled by fetchMeAndMaybeShowAdmin
}

