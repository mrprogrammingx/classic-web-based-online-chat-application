// Composer/send logic extracted from app.js
(function(){
  async function handleComposerSubmit(e){
    try{ e.preventDefault(); }catch(e){}
    try{
      // gentle local send timestamp
      try{ window.lastLocalSendAt = Date.now(); }catch(e){}
      const btn = document.getElementById('unread-total');
      if(btn){ btn.classList.remove('pulse-local'); void btn.offsetWidth; btn.classList.add('pulse-local'); setTimeout(()=>btn.classList.remove('pulse-local'), 600); }
    }catch(e){}
    const input = document.getElementById('message-input');
    const text = input ? input.value.trim() : '';
    const composerEl = document.getElementById('composer');
    const replyTo = composerEl && composerEl.dataset && composerEl.dataset.replyTo || null;
    const fileEl = document.getElementById('file-input');
    const fileSelected = fileEl && fileEl.files && fileEl.files.length > 0;
    if(!text && !fileSelected) return;
    // create placeholder
    const placeholder = document.createElement('div'); placeholder.className = 'message pending me';
    const phMeta = document.createElement('div'); phMeta.className='meta'; phMeta.textContent = 'you';
    const phBody = document.createElement('div'); phBody.className='body'; phBody.textContent = text || '';
    placeholder.appendChild(phMeta); placeholder.appendChild(phBody);
    // controls
    const controls = document.createElement('div'); controls.className='controls';
    const status = document.createElement('span'); status.className='status'; controls.appendChild(status);
    const retryBtn = document.createElement('button'); retryBtn.type='button'; retryBtn.textContent='Retry';
    const cancelBtn = document.createElement('button'); cancelBtn.type='button'; cancelBtn.textContent='Cancel';
    controls.appendChild(retryBtn); controls.appendChild(cancelBtn);
    placeholder.appendChild(controls);
    try{ if(window.messagesEl) window.messagesEl.appendChild(placeholder); }catch(e){}
    try{ if(window.autoscroll) window.messagesEl.scrollTop = window.messagesEl.scrollHeight; }catch(e){}

    // prepare payload
    const payload = { text };
    if(replyTo) payload.reply_to = Number(replyTo);
    if(!window.currentRoom) return;

    // helper to cleanup placeholder on error
    function removePlaceholder(){ try{ if(placeholder && placeholder.parentNode) placeholder.parentNode.removeChild(placeholder); }catch(e){} }

    if(fileSelected){
      const file = fileEl.files[0];
      const fd = new FormData();
      fd.append('text', text);
      if(replyTo) fd.append('reply_to', replyTo);
      fd.append('file', file, file.name);
      const progressWrap = document.createElement('div'); progressWrap.className='attachment-progress'; progressWrap.textContent = `Uploading ${file.name}: `;
      const prog = document.createElement('progress'); prog.max = 100; prog.value = 0; progressWrap.appendChild(prog);
      try{ if(window.messagesEl) window.messagesEl.appendChild(progressWrap); }catch(e){}
      const url = window.isDialog ? `/dialogs/${window.currentRoom.id}/messages_with_file` : `/rooms/${window.currentRoom.id}/messages_with_file`;
      const xhr = new XMLHttpRequest();
      xhr.open('POST', url);
      xhr.onload = function(){
        try{
          const json = JSON.parse(xhr.responseText);
          if(json && json.message){ const fullMsg = Object.assign({}, json.message); if(json.file) fullMsg.files = [json.file]; const el2 = window.appendMessage(fullMsg); try{ window.messagesEl.replaceChild(el2, placeholder); }catch(e){} try{ window.latestTimestamp = json.message.created_at || window.latestTimestamp; }catch(e){} }
        }catch(e){ console.error('parse response', e); }
        try{ progressWrap.remove(); }catch(e){}
      };
      xhr.onerror = function(){ window.showToast && window.showToast('Upload failed', 'error'); try{ progressWrap.remove(); }catch(e){} };
      xhr.addEventListener('error', ()=>{ if(placeholder){ placeholder.classList.add('failed'); status.textContent = 'Failed'; window.showToast && window.showToast('Upload failed', 'error'); } });
      xhr.upload.onprogress = function(ev){ if(ev.lengthComputable){ const pct = Math.round((ev.loaded/ev.total)*100); prog.value = pct; } };
      xhr.send(fd);
      retryBtn.addEventListener('click', ()=>{ if(placeholder) placeholder.classList.remove('failed'); status.textContent = ''; composerEl.querySelector('button[type=submit]').click(); });
      cancelBtn.addEventListener('click', ()=>{ removePlaceholder(); });
    } else {
      const url = window.isDialog ? `/dialogs/${window.currentRoom.id}/messages` : `/rooms/${window.currentRoom.id}/messages`;
      fetch(url, {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(payload)})
        .then(r=>r.json())
        .then(json=>{
          if(json && json.message){ const fullMsg = Object.assign({}, json.message); const el2 = window.appendMessage(fullMsg); try{ window.messagesEl.replaceChild(el2, placeholder); }catch(e){} try{ window.latestTimestamp = json.message.created_at || window.latestTimestamp; }catch(e){} try{ if(window.autoscroll) window.messagesEl.scrollTop = window.messagesEl.scrollHeight; }catch(e){} }
        }).catch(err=>{ console.error('send message failed', err); removePlaceholder(); });
    }

    // clear reply preview
    const replyPreviewEl = document.getElementById('reply-preview'); if(replyPreviewEl) replyPreviewEl.style.display = 'none';
    try{ delete composerEl.dataset.replyTo; }catch(e){}
  }

  try{ window.handleComposerSubmit = handleComposerSubmit; }catch(e){}
})();
