const BASE = location.origin;
let token = null;
let jti = null;
let tabId = 'tab-' + Math.random().toString(36).slice(2,9);

async function register(){
  const email = document.getElementById('email').value;
  const username = document.getElementById('username').value;
  const password = document.getElementById('password').value;
  const r = await fetch(BASE + '/register', {method:'POST', headers:{'content-type':'application/json'}, body: JSON.stringify({email, username, password})});
  const data = await r.json();
  if(r.status===200){
    token = data.token;
    jti = data.token && parseJwt(data.token).jti;
    onLogin(data.user);
  } else {
    alert(JSON.stringify(data));
  }
}

async function login(){
  const email = document.getElementById('email').value;
  const password = document.getElementById('password').value;
  const r = await fetch(BASE + '/login', {method:'POST', headers:{'content-type':'application/json'}, body: JSON.stringify({email, password})});
  const data = await r.json();
  if(r.status===200){
    token = data.token;
    jti = data.token && parseJwt(data.token).jti;
    onLogin(data.user);
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
  document.getElementById('auth').style.display='none';
  document.getElementById('me').style.display='block';
  document.getElementById('me-name').textContent = user.username;
  startHeartbeat();
}

async function heartbeat(){
  if(!token || !jti) return;
  await fetch(BASE + '/presence/heartbeat', {method:'POST', headers:{'content-type':'application/json','Authorization':'Bearer ' + token}, body: JSON.stringify({tab_id: tabId, jti})});
}

function startHeartbeat(){
  heartbeat();
  window._hb = setInterval(heartbeat, 20000);
}

window.addEventListener('beforeunload', async ()=>{
  try{ await fetch(BASE + '/presence/close', {method:'POST', headers:{'content-type':'application/json','Authorization':'Bearer ' + token}, body: JSON.stringify({tab_id: tabId})}); }catch(e){}
});

document.getElementById('register').onclick = register;
document.getElementById('login').onclick = login;
document.getElementById('list-sessions').onclick = listSessions;

document.getElementById('logout').onclick = async ()=>{
  await fetch(BASE + '/logout', {method:'POST', headers:{'Authorization':'Bearer ' + token}});
  token = null; jti = null; document.getElementById('auth').style.display='block'; document.getElementById('me').style.display='none';
}
