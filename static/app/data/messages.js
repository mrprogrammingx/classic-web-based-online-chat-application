// Extracted message rendering helpers (minimal, global-exporting shim)
(function(){
  // Append a message element to the message list and return the element
  function appendMessage(m){
    try{
      // Debug: emit a short console message so E2E traces capture when messages are
      // rendered. This helps diagnose timing issues in Playwright tests.
      try{ console.debug && console.debug('appendMessage', (m && (m.text || m.id || m.user_id)) ); }catch(e){}
      const wrap = document.createElement('div');
      // use String-safe comparison so numeric vs string id types don't prevent the 'me' class
      wrap.className = 'message ' + ((m.user_id && window.__ME_ID && String(m.user_id) === String(window.__ME_ID)) ? 'me' : '');
      const meta = document.createElement('div'); meta.className = 'meta';
      const who = document.createElement('strong');
      // If this message is from the current user, show a friendly label instead of the raw username
      var isMe = false;
      try{
        // Prefer server-provided display_name, then username, then fall back to id
        const authorName = m.display_name || m.username || m.user_name || null;
        if(window.__ME_ID && m.user_id && String(m.user_id) === String(window.__ME_ID)){
          who.textContent = 'Me';
          isMe = true;
        } else {
          who.textContent = authorName || m.user_id || ('user'+(m.user_id||''));
        }
      }catch(e){ who.textContent = m.display_name || m.username || m.user_id || ('user'+(m.user_id||'')); }
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
          // prefer display_name on reply preview when available
          const replyAuthor = (m.reply && (m.reply.display_name || m.reply.username || m.reply.user_name)) ? (m.reply.display_name || m.reply.username || m.reply.user_name) : (m.reply && m.reply.user_id ? m.reply.user_id : 'user');
          const rph = document.createElement('div'); rph.className = 'reply-author'; rph.textContent = replyAuthor + ':';
          const rpt = document.createElement('div'); rpt.className = 'reply-text'; rpt.textContent = m.reply.text || '';
          rp.appendChild(rph); rp.appendChild(rpt);
          wrap.appendChild(rp);
        }catch(e){}
      }
      body.textContent = m.text || '';
      // render attachments if present: images inline, other files as links
      try{
        if(m.files && Array.isArray(m.files) && m.files.length){
          const attachWrap = document.createElement('div'); attachWrap.className = 'attachment';
          m.files.forEach(f => {
            try{
              // server returns a `url` field for the file when uploaded
              const fileUrl = f.url || f.path || null;
              const origName = f.original_filename || f.name || '';
              if(fileUrl && String((f.mime || '')).indexOf('image/') === 0){
                const img = document.createElement('img'); img.src = fileUrl; img.alt = origName; img.style.maxWidth = '200px'; img.style.borderRadius = '8px'; attachWrap.appendChild(img);
              } else if(fileUrl && (origName || fileUrl)){
                const a = document.createElement('a'); a.className = 'file-link'; a.href = fileUrl; a.textContent = origName || fileUrl; a.target = '_blank'; attachWrap.appendChild(a);
              }
            }catch(e){}
          });
          if(attachWrap.childElementCount) wrap.appendChild(attachWrap);
        }
      }catch(e){}
      wrap.appendChild(meta); wrap.appendChild(body);
      try{ if(m.id) wrap.dataset.id = String(m.id); }catch(e){}
      return wrap;
    }catch(e){ console.warn('appendMessage failed', e); const r = document.createElement('div'); r.textContent = m && (m.text || JSON.stringify(m)) || ''; return r; }
  }

  // expose globally for the legacy app.js to call
  try{ window.appendMessage = appendMessage; }catch(e){ /* ignore */ }
})();
