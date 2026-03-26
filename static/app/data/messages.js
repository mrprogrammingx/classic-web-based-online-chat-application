// Extracted message rendering helpers (minimal, global-exporting shim)
(function(){
  // Append a message element to the message list and return the element
  function appendMessage(m){
    try{
      const wrap = document.createElement('div');
      // use String-safe comparison so numeric vs string id types don't prevent the 'me' class
      wrap.className = 'message ' + ((m.user_id && window.__ME_ID && String(m.user_id) === String(window.__ME_ID)) ? 'me' : '');
      const meta = document.createElement('div'); meta.className = 'meta';
      const who = document.createElement('strong');
      // If this message is from the current user, show a friendly label instead of the raw username
      var isMe = false;
      try{
        if(window.__ME_ID && m.user_id && String(m.user_id) === String(window.__ME_ID)){
          who.textContent = 'Me';
          isMe = true;
        } else {
          who.textContent = m.username || m.user_id || ('user'+(m.user_id||''));
        }
      }catch(e){ who.textContent = m.username || m.user_id || ('user'+(m.user_id||'')); }
      const time = document.createElement('span'); time.className = 'time'; time.textContent = m.created_at ? (new Date(m.created_at).toLocaleString()) : '';
      // small circular avatar for message (single-letter initial). We'll insert it into meta
      const avatar = document.createElement('span'); avatar.className = 'msg-avatar';
      try{
        // pick an initial: prefer username when available, fall back to 'M' for Me or user id
        const nameForInitial = isMe ? (window.__ME_NAME || m.username || 'Me') : (m.username || String(m.user_id || 'U'));
        avatar.textContent = String(nameForInitial).charAt(0).toUpperCase();
      }catch(e){ avatar.textContent = 'U'; }
      // append avatar then author
      meta.appendChild(avatar);
      meta.appendChild(who);
      // if this is the current user's message, append a small 'You' badge
      if(isMe){
        try{
          const you = document.createElement('span'); you.className = 'you-badge'; you.textContent = 'You'; meta.appendChild(document.createTextNode(' ')); meta.appendChild(you);
        }catch(e){}
      }
      meta.appendChild(document.createTextNode(' ')); meta.appendChild(time);
      const body = document.createElement('div'); body.className = 'body';
      // if this message has a reply preview object, render it above the body
      if(m.reply){
        try{
          const rp = document.createElement('div'); rp.className = 'reply-preview';
          const rpt = document.createElement('div'); rpt.className = 'reply-text'; rpt.textContent = m.reply.text || '';
          rp.appendChild(rpt);
          wrap.appendChild(rp);
        }catch(e){}
      }
      body.textContent = m.text || '';
      wrap.appendChild(meta); wrap.appendChild(body);
      try{ if(m.id) wrap.dataset.id = String(m.id); }catch(e){}
      return wrap;
    }catch(e){ console.warn('appendMessage failed', e); const r = document.createElement('div'); r.textContent = m && (m.text || JSON.stringify(m)) || ''; return r; }
  }

  // expose globally for the legacy app.js to call
  try{ window.appendMessage = appendMessage; }catch(e){ /* ignore */ }
})();
