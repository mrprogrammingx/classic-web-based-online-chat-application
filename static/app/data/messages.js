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
      // show an "edited" indicator when the message has been edited
      try{
        if(m && (m.edited_at || m.edited)){
          const editedSpan = document.createElement('span');
          editedSpan.className = 'edited';
          editedSpan.textContent = ' (edited)';
          meta.appendChild(editedSpan);
        }
      }catch(e){}
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
      // actions container: Edit/Delete buttons (visible to appropriate users)
      try{
        const actions = document.createElement('div'); actions.className = 'msg-actions';
        // only render when we have an id
        if(m.id){
          // Edit button: visible only to message author
          if(window && window.__ME_ID && String(m.user_id) === String(window.__ME_ID)){
            const editBtn = document.createElement('button'); editBtn.className = 'btn btn-link msg-edit'; editBtn.textContent = 'Edit';
            editBtn.addEventListener('click', async (ev)=>{
              try{
                ev && ev.preventDefault && ev.preventDefault();
                const curText = m.text || '';
                // prefer modal if available
                let newText = null;
                if(window && typeof window.showModal === 'function'){
                  // Capture existing textareas so we can detect the one the modal
                  // inserts. Some modal implementations don't preserve the id or
                  // insert inside containers, so diffing lists is more reliable.
                  const beforeTextareas = Array.from(document.querySelectorAll('textarea'));

                  // Open the modal but don't await it yet — this lets us run
                  // code to find and populate the textarea before the user
                  // interacts. Some modal implementations sanitize innerHTML
                  // so setting the initial value proactively is necessary.
                  const modalPromise = window.showModal({ title: 'Edit message', body: `<textarea style="width:100%" id="__edit_msg_input">${curText.replace(/</g,'&lt;')}</textarea>`, html: true, confirmText: 'Save', cancelText: 'Cancel' });

                  // Poll briefly for the textarea that the modal inserted so
                  // we can set its initial value (if empty) before the user types.
                  let ta = null;
                  const startOpen = Date.now();
                  const openTimeoutMs = 1000;
                  const intervalMs = 40;
                  while((Date.now() - startOpen) < openTimeoutMs && !ta){
                    await new Promise(r => setTimeout(r, intervalMs));
                    try{
                      const nowTextareas = Array.from(document.querySelectorAll('textarea'));
                      ta = nowTextareas.find(t => beforeTextareas.indexOf(t) === -1) || null;
                    }catch(e){ ta = null; }
                  }
                  // fallback if diff didn't find it
                  if(!ta){
                    ta = document.getElementById('__edit_msg_input') || (function(){ try{ return document.querySelector('textarea#__edit_msg_input, textarea.modal-input, #__modal textarea, textarea'); }catch(e){ return null; } })();
                  }
                  try{ console.debug && console.debug('message-edit: textarea before user', !!ta, ta && ta.value); }catch(e){}
                  if(ta){
                    try{
                      if(!ta.value) {
                        ta.value = curText;
                        try{ console.debug && console.debug('message-edit: textarea set initial value', ta.value); }catch(e){}
                      }
                      // Install document-level capture listeners to record the
                      // live value as the user types. This is robust against
                      // DOM recreation because the handlers are on document.
                      try{ window.__edit_modal_last_value = ta.value; }catch(e){}
                      const captureHandler = (ev) => {
                        try{
                          const t = ev && ev.target;
                          if(!t) return;
                          const tag = (t.tagName || '').toLowerCase();
                          let v = null;
                          if(tag === 'textarea' || tag === 'input') v = t.value;
                          else if(t.isContentEditable) v = t.textContent;
                          else if(t.querySelector) {
                            const inp = t.querySelector('textarea, input');
                            if(inp) v = inp.value;
                          }
                          if(v !== null && v !== undefined) window.__edit_modal_last_value = v;
                        }catch(e){}
                      };
                      document.addEventListener('input', captureHandler, true);
                      document.addEventListener('keyup', captureHandler, true);
                      // poll activeElement as a last resort
                      const pollInterval = setInterval(()=>{
                        try{
                          const ae = document.activeElement;
                          if(ae){ const tag = (ae.tagName||'').toLowerCase(); if(tag==='textarea' || tag==='input') window.__edit_modal_last_value = ae.value; else if(ae.isContentEditable) window.__edit_modal_last_value = ae.textContent; }
                        }catch(e){}
                      }, 80);
                      try{ window.__edit_modal_last_value_cleanup = () => { try{ clearInterval(pollInterval); document.removeEventListener('input', captureHandler, true); document.removeEventListener('keyup', captureHandler, true); }catch(e){} }; }catch(e){}
                    }catch(e){}
                  }

                  // Now wait for the modal to resolve (user interaction)
                  const ok = await modalPromise;
                  try{ console.debug && console.debug('message-edit: modal resolved', { ok }); }catch(e){}
                  if(!ok) return;

                  // Re-query the textarea after the modal confirmed, because
                  // some implementations recreate the DOM on confirm. Read the
                  // latest value so we get what the user actually typed.
                  let finalTa = document.getElementById('__edit_msg_input');
                  if(!finalTa){ try{ finalTa = document.querySelector('textarea#__edit_msg_input, textarea.modal-input, #__modal textarea, textarea'); }catch(e){ finalTa = null; } }
                  // If the DOM was recreated, try to match by position: look for
                  // a textarea that wasn't present before (again).
                  if(!finalTa){
                    try{
                      const laterTextareas = Array.from(document.querySelectorAll('textarea'));
                      finalTa = laterTextareas.find(t => beforeTextareas.indexOf(t) === -1) || null;
                    }catch(e){ finalTa = null; }
                  }
                  // Prefer the live-stored value captured during user input. If
                  // that's not available, fall back to robust DOM reads that
                  // handle textarea/input/contenteditable cases.
                  try{
                    // try stored live value first
                    let finalVal = null;
                    try{ if(window && window.__edit_modal_last_value !== undefined) finalVal = window.__edit_modal_last_value; }catch(e){ finalVal = null; }
                    // cleanup any polling/listeners
                    try{ if(window && window.__edit_modal_last_value_cleanup) { window.__edit_modal_last_value_cleanup(); delete window.__edit_modal_last_value_cleanup; } }catch(e){}
                    if(finalVal == null){
                      const readEditable = (el) => {
                        if(!el) return null;
                        try{
                          const tag = (el.tagName || '').toLowerCase();
                          if(tag === 'textarea' || tag === 'input') return el.value || el.getAttribute('value') || null;
                          if(el.isContentEditable) return el.textContent || el.innerText || null;
                          const inp = el.querySelector && (el.querySelector('input, textarea'));
                          if(inp) return inp.value || inp.getAttribute('value') || null;
                          return el.value || (el.getAttribute && el.getAttribute('value')) || el.textContent || null;
                        }catch(e){ return null; }
                      };
                      const finalRead = readEditable(finalTa);
                      if(finalRead != null) finalVal = finalRead;
                      else {
                        try{
                          const laterTextareas = Array.from(document.querySelectorAll('textarea'));
                          const recreated = laterTextareas.find(t => beforeTextareas.indexOf(t) === -1) || null;
                          const recreatedVal = readEditable(recreated);
                          if(recreatedVal != null) finalVal = recreatedVal;
                        }catch(e){}
                      }
                    }
                    try{ console.debug && console.debug('message-edit: final value read', { finalVal }); }catch(e){}
                    if(finalVal != null) newText = finalVal;
                    try{ if(window && window.__edit_modal_last_value !== undefined) delete window.__edit_modal_last_value; }catch(e){}
                  }catch(e){}
                } else {
                  newText = window.prompt('Edit message', curText);
                }
                if(newText == null) return;
                // call edit endpoint
                const payload = { text: newText };
                // prefer explicit message.room_id, fall back to window.currentRoom.id or other heuristics
                const roomIdUsed = (m && (m.room_id || m.room || m.roomId)) || (window && window.currentRoom && window.currentRoom.id) || undefined;
                const endpoint = roomIdUsed ? `/rooms/${roomIdUsed}/messages/${m.id}/edit` : `/messages/${m.id}/edit`;
                try{ console.debug && console.debug('message-edit: about to POST', endpoint, payload); }catch(e){}
                const res = await window.fetchJSON(endpoint, { method: 'POST', body: JSON.stringify(payload), headers: { 'Content-Type': 'application/json' } });
                try{ console.debug && console.debug('message-edit: fetchJSON result', res); }catch(e){}
                if(res && res.message){
                  m.text = res.message.text || newText;
                  // server may return edited_at; set it locally as a fallback
                  m.edited_at = res.message.edited_at || (new Date()).toISOString();

                  // ── Update the live DOM node ───────────────────────────────
                  // Find the message element in the *current* DOM via data-id so
                  // we update the correct node even if the poller has rebuilt the
                  // list since appendMessage was called (which orphans the
                  // closed-over `body` / `wrap` references).
                  try{
                    const messagesContainer = (window.messagesEl) || document.getElementById('messages');
                    const liveWrap = (messagesContainer && m.id)
                      ? messagesContainer.querySelector('[data-id="' + String(m.id) + '"]')
                      : null;
                    const targetWrap = (liveWrap && liveWrap.isConnected) ? liveWrap
                      : ((wrap && wrap.isConnected) ? wrap : null);
                    if(targetWrap){
                      // update text
                      const bodyEl = targetWrap.querySelector('.body');
                      if(bodyEl) bodyEl.textContent = m.text || '';
                      // add or refresh "(edited)" indicator in .meta
                      const metaEl = targetWrap.querySelector('.meta');
                      if(metaEl){
                        let ed = metaEl.querySelector('.edited');
                        if(!ed){
                          ed = document.createElement('span');
                          ed.className = 'edited';
                          ed.textContent = ' (edited)';
                          metaEl.appendChild(ed);
                        }
                      }
                    } else {
                      // targetWrap is gone (e.g. room switched) — nothing to update
                    }
                  }catch(e){ console.warn('message-edit: DOM update failed', e); }
                  // ── end live DOM update ────────────────────────────────────

                  window.showToast && window.showToast('Message edited','success');
                } else {
                  window.showToast && window.showToast('Failed to edit message','error');
                }
              }catch(e){ console.warn('edit action failed', e); window.showToast && window.showToast('Edit failed','error'); }
            });
            actions.appendChild(editBtn);
          }
          // Delete button: visible to author or room owner/admin (best-effort client-side)
          try{
            const canDeleteClient = (window && window.__ME_ID && String(m.user_id) === String(window.__ME_ID)) || (window && window.currentRoom && (String(window.currentRoom.owner) === String(window.__ME_ID) || (window.currentRoom.admins && Array.isArray(window.currentRoom.admins) && window.currentRoom.admins.indexOf(window.__ME_ID) !== -1)));
            if(canDeleteClient){
              const delBtn = document.createElement('button'); delBtn.className = 'btn btn-link msg-delete'; delBtn.textContent = 'Delete';
              delBtn.addEventListener('click', async (ev)=>{
                try{
                  ev && ev.preventDefault && ev.preventDefault();
                  let ok = true;
                  try{ ok = await (window.showModal ? window.showModal({ title: 'Delete message', body: 'Delete this message? This cannot be undone.', confirmText: 'Delete', cancelText: 'Cancel' }) : Promise.resolve(window.confirm('Delete this message?'))); }catch(e){ ok = true; }
                  if(!ok) return;
                  // prefer explicit message.room_id, fall back to window.currentRoom.id
                  const roomIdUsedDel = (m && (m.room_id || m.room || m.roomId)) || (window && window.currentRoom && window.currentRoom.id) || undefined;
                  const delEndpoint = roomIdUsedDel ? `/rooms/${roomIdUsedDel}/messages/${m.id}` : `/messages/${m.id}`;
                  try{ console.debug && console.debug('message-delete: about to DELETE', delEndpoint); }catch(e){}
                  const r = await fetch(delEndpoint, { method: 'DELETE', credentials: 'include', headers: { 'Content-Type': 'application/json' } });
                  try{ console.debug && console.debug('message-delete: delete response', r && r.status); }catch(e){}
                  if(r && r.ok){
                    try{ if(wrap && wrap.parentElement) wrap.parentElement.removeChild(wrap); }catch(e){}
                    window.showToast && window.showToast('Message deleted','success');
                  } else {
                    window.showToast && window.showToast('Failed to delete message','error');
                  }
                }catch(e){ console.warn('delete action failed', e); window.showToast && window.showToast('Delete failed','error'); }
              });
              actions.appendChild(delBtn);
            }
          }catch(e){}
        }
        if(actions.childElementCount) wrap.appendChild(actions);
      }catch(e){}
      try{ if(m.id) wrap.dataset.id = String(m.id); }catch(e){}
      return wrap;
    }catch(e){ console.warn('appendMessage failed', e); const r = document.createElement('div'); r.textContent = m && (m.text || JSON.stringify(m)) || ''; return r; }
  }

  // expose globally for the legacy app.js to call
  try{ window.appendMessage = appendMessage; }catch(e){ /* ignore */ }
})();
