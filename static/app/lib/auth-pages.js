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

  try{ window.initAuthPages = setupAuthPageHelpers; window.register = register; window.login = login; }catch(e){}
})();
