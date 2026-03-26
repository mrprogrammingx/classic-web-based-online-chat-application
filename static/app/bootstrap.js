// bootstrap/auth loader (moved out of app.js)
(function(){
  async function bootstrap(){
    try{
      const r = await fetch('/refresh', {method: 'POST', credentials: 'include'}).catch(()=>null);
      if(!r || r.status === 401){
        // redirect to the hosted login page which will set cookie on success
        location.href = '/static/auth/login.html';
        return;
      }
      // if logged in, the response contains token and user metadata
      try{
        const body = await r.json();
        const user = body.user;
        if(user){
          const ui = document.getElementById('user-info');
          if(ui){
            try{
              if(window && typeof window.renderUserInfo === 'function'){
                window.renderUserInfo(user);
              } else {
                // minimal fallback
                ui.textContent = (user.username || user.email || ('user'+user.id));
              }
            }catch(e){ console.warn('renderUserInfo failed', e); }
          }
        }
      }catch(e){ console.warn('refresh parse failed', e); }
      // ready: load data
      try{ if(window && typeof window.loadRooms === 'function') await window.loadRooms(); }catch(e){}
      try{ if(window && typeof window.loadContacts === 'function') await window.loadContacts(); }catch(e){}
      // update unread notification badges
      try{ if(typeof loadUnreadSummary === 'function') await loadUnreadSummary(); }catch(e){}
    }catch(e){ console.warn('bootstrap failed', e); }
  }

  try{ window.bootstrap = bootstrap; }catch(e){}
})();
