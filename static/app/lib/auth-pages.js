// Helpers for auth pages (login/register)
(function(){
  function setupAuthPageHelpers(){
    try{
      const email = document.getElementById('email');
      if(email) email.focus();
      document.addEventListener('keydown', (e)=>{
        if(e.key === 'Enter'){
          const active = document.activeElement;
          if(active && active.tagName && active.tagName.toLowerCase() === 'textarea') return;
          const login = document.getElementById('login');
          const reg = document.getElementById('register');
          if(login && document.getElementById('email')) { login.click(); }
          else if(reg && document.getElementById('username')) { reg.click(); }
        }
      });
    }catch(e){}
  }

  async function register(){
    try{
      const BASE = location.origin;
      const email = document.getElementById('email').value;
      const username = document.getElementById('username').value;
      const password = document.getElementById('password').value;
      const r = await fetch(BASE + '/register', {method:'POST', credentials:'include', headers:{'content-type':'application/json'}, body: JSON.stringify({email, username, password})});
      const data = await r.json();
      if(r.status===200){
        try{ sessionStorage.setItem('boot_user', JSON.stringify(data.user)); sessionStorage.setItem('boot_token', data.token || ''); const pj = data.token ? JSON.parse(atob(data.token.split('.')[1])) : {}; sessionStorage.setItem('boot_jti', pj.jti || ''); }catch(e){}
        location.href = (window.siteHref ? window.siteHref('homeHref','/static/home.html') : '/static/home.html');
      } else { try{ await (window.showAlert ? window.showAlert(JSON.stringify(data), 'Registration failed') : Promise.resolve()); }catch(e){} }
    }catch(e){ console.warn('register failed', e) }
  }

  async function login(){
    try{
      const BASE = location.origin;
      const email = document.getElementById('email').value;
      const password = document.getElementById('password').value;
      const r = await fetch(BASE + '/login', {method:'POST', credentials:'include', headers:{'content-type':'application/json'}, body: JSON.stringify({email, password})});
      const data = await r.json();
      if(r.status===200){ try{ sessionStorage.setItem('boot_user', JSON.stringify(data.user)); sessionStorage.setItem('boot_token', data.token || ''); const pj = data.token ? JSON.parse(atob(data.token.split('.')[1])) : {}; sessionStorage.setItem('boot_jti', pj.jti || ''); }catch(e){} location.href = (window.siteHref ? window.siteHref('homeHref','/static/home.html') : '/static/home.html'); } else { try{ await (window.showAlert ? window.showAlert(JSON.stringify(data), 'Login failed') : Promise.resolve()); }catch(e){} }
    }catch(e){ console.warn('login failed', e) }
  }

  async function requestReset(){
    try{
      const BASE = location.origin;
      const email = document.getElementById('email').value;
      const r = await fetch(BASE + '/password/reset-request', {method:'POST', credentials:'include', headers:{'content-type':'application/json'}, body: JSON.stringify({email})});
      const data = await r.json();
      const note = document.getElementById('reset-note');
      if(r.status===200){
        if(note) note.textContent = 'If an account exists, a reset link was issued.';
        // In TEST_MODE the token may be returned; show it for convenience
        if(data && data.token) try{ if(note) note.textContent += ' Token: ' + data.token; }catch(e){}
      } else {
        let msg = 'Request failed';
        try{ msg = JSON.stringify(data); }catch(e){}
        if(note) note.textContent = msg;
      }
    }catch(e){ console.warn('reset request failed', e); }
  }

  async function performReset(){
    try{
      const BASE = location.origin;
      const token = document.getElementById('token').value;
      const password = document.getElementById('password').value;
      const r = await fetch(BASE + '/password/reset', {method:'POST', credentials:'include', headers:{'content-type':'application/json'}, body: JSON.stringify({token, password})});
      const data = await r.json().catch(()=>null);
      const note = document.getElementById('reset-note');
  if(r.status===200){ if(note) note.textContent = 'Password updated. You can now login.'; } else { let msg = data || {error:'failed'}; try{ msg = JSON.stringify(msg); }catch(e){} if(note) note.textContent = msg; }
    }catch(e){ console.warn('reset failed', e); }
  }

  try{ window.initAuthPages = setupAuthPageHelpers; window.register = register; window.login = login; window.requestReset = requestReset; window.performReset = performReset; }catch(e){}
})();
