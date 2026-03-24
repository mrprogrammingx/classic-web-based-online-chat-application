document.addEventListener('DOMContentLoaded', ()=>{
  const roomsList = document.getElementById('rooms-list');
  const contactsList = document.getElementById('contacts-list');
  const membersList = document.getElementById('members-list');
  const messagesEl = document.getElementById('messages');
  const roomTitle = document.getElementById('room-title');
  const composer = document.getElementById('composer');
  const input = document.getElementById('message-input');
  const roomsSection = document.getElementById('rooms-section');
  const roomsToggle = document.getElementById('rooms-toggle');

  // runtime state
  let rooms = [];
  let contacts = [];
  let isDialog = false;

  function renderRooms(){
    roomsList.innerHTML = '';
    rooms.forEach(r=>{
      const li = document.createElement('li');
      li.textContent = r.name;
      li.dataset.id = r.id;
      li.addEventListener('click', ()=>selectRoom(r));
      roomsList.appendChild(li);
    });
  }
  function renderMembers(list){
    membersList.innerHTML = '';
    list.forEach(m=>{
      const li = document.createElement('li');
      const dot = document.createElement('span');
      dot.className = 'online-dot ' + (m.online? 'online':'offline');
      li.appendChild(dot);
      const txt = document.createTextNode(m.name);
      li.appendChild(txt);
      membersList.appendChild(li);
    });
  }
  function renderContacts(){
    contactsList.innerHTML = '';
    contacts.forEach(c=>{
      const li = document.createElement('li');
      li.textContent = c.name;
      li.dataset.id = c.id;
      li.addEventListener('click', ()=>openDialog(c));
      contactsList.appendChild(li);
    });
  }

  let currentRoom = null;
  function selectRoom(r){
    isDialog = false;
    currentRoom = r;
    roomTitle.textContent = r.name;
    messagesEl.innerHTML = '';
    // compact rooms into accordion style
    roomsSection.classList.add('compacted');
    // load messages for this room
    loadRoomMessages(r.id);
    // load members and presence
    loadRoomMembers(r.id);
  }
  function openDialog(contact){
    isDialog = true;
    currentRoom = {id: contact.id, name: contact.name};
    roomTitle.textContent = contact.name + ' (dialog)';
    messagesEl.innerHTML = '';
    loadDialogMessages(contact.id);
  }

  function appendMessage(msg){
    const el = document.createElement('div');
    el.className = 'message' + (msg.user==='me'? ' me':'');
    // metadata (author)
    const meta = document.createElement('div');
    meta.className = 'meta';
    if(msg.user && msg.user!=='system') meta.textContent = msg.user;
    else if(msg.user_id) meta.textContent = 'user ' + msg.user_id;
    else meta.textContent = '';
    el.appendChild(meta);

    // reply preview if present
    if(msg.reply){
      const rp = document.createElement('div');
      rp.className = 'reply-preview';
      const rpAuthor = document.createElement('div'); rpAuthor.className='reply-author'; rpAuthor.textContent = msg.reply.user_id ? ('user ' + msg.reply.user_id) : '';
      const rpText = document.createElement('div'); rpText.className='reply-text'; rpText.textContent = msg.reply.text || '';
      rp.appendChild(rpAuthor);
      rp.appendChild(rpText);
      el.appendChild(rp);
    }

    const body = document.createElement('div');
    body.className = 'body';
    body.textContent = msg.text;
    el.appendChild(body);

    // allow clicking a message to reply
    el.addEventListener('click', ()=>{
      const replyPreview = document.getElementById('reply-preview');
      const replyAuthor = document.getElementById('reply-to-author');
      const replyText = document.getElementById('reply-to-text');
      if(msg.user || msg.user_id){
        replyAuthor.textContent = msg.user || ('user ' + (msg.user_id||''));
      } else replyAuthor.textContent = 'message';
      replyText.textContent = msg.text || '';
      replyPreview.style.display = 'flex';
      const composer = document.getElementById('composer');
      composer.dataset.replyTo = msg.id || '';
    });
    // render attachments if present
    if(msg.files && msg.files.length){
      const attWrap = document.createElement('div'); attWrap.className='attachment';
      msg.files.forEach(f => {
        const lower = (f.original_filename || f.path || '').toLowerCase();
        const isImage = lower.match(/\.(png|jpe?g|gif|webp)$/);
        const url = f.url || (`/dialogs/${f.to_id}/files/${f.id}`);
        if(isImage){
          const img = document.createElement('img');
          img.src = url;
          attWrap.appendChild(img);
        } else {
          const a = document.createElement('a'); a.href = url; a.className='file-link'; a.textContent = f.original_filename || 'file'; a.target='_blank';
          attWrap.appendChild(a);
        }
      });
      el.appendChild(attWrap);
    }
    // return element so caller can decide to append or prepend
    return el;
  }

  // autoscroll logic: only auto-scroll when user is at or near bottom
  let autoscroll = true;
  function userIsAtBottom(){
    const threshold = 40; // px
    return messagesEl.scrollHeight - messagesEl.scrollTop - messagesEl.clientHeight < threshold;
  }
  messagesEl.addEventListener('scroll', ()=>{
    // if user scrolls up, disable autoscroll
    autoscroll = userIsAtBottom();
    // infinite scroll trigger: when near top, load older messages
    if(messagesEl.scrollTop < 50 && currentRoom){
      // load older messages
      if(isDialog){
        loadDialogMessages(currentRoom.id, {before: earliestTimestamp, prepend: true});
      } else {
        loadRoomMessages(currentRoom.id, {before: earliestTimestamp, prepend: true});
      }
    }
  });

  // track earliest message timestamp currently rendered for infinite scroll
  let earliestTimestamp = null;
  let latestTimestamp = null;

  composer.addEventListener('submit', (e)=>{
    e.preventDefault();
    const text = input.value.trim();
    const composerEl = document.getElementById('composer');
    const replyTo = composerEl.dataset.replyTo || null;
    const fileEl = document.getElementById('file-input');
    const fileSelected = fileEl && fileEl.files && fileEl.files.length > 0;
    if(!text && !fileSelected) return;
  // create a pending placeholder instead of optimistic duplicate append
  const placeholder = document.createElement('div');
  placeholder.className = 'message pending me';
  const phMeta = document.createElement('div'); phMeta.className='meta'; phMeta.textContent = 'you';
  const phBody = document.createElement('div'); phBody.className='body'; phBody.textContent = text || '';
  placeholder.appendChild(phMeta);
  placeholder.appendChild(phBody);
  // controls for retry/cancel
  const controls = document.createElement('div'); controls.className='controls';
  const status = document.createElement('span'); status.className='status';
  controls.appendChild(status);
  const retryBtn = document.createElement('button'); retryBtn.type='button'; retryBtn.textContent='Retry';
  const cancelBtn = document.createElement('button'); cancelBtn.type='button'; cancelBtn.textContent='Cancel';
  controls.appendChild(retryBtn);
  controls.appendChild(cancelBtn);
  placeholder.appendChild(controls);
  messagesEl.appendChild(placeholder);
  if(autoscroll) messagesEl.scrollTop = messagesEl.scrollHeight;
    // prepare payload
    const payload = { text };
    if(replyTo) payload.reply_to = Number(replyTo);
    input.value = '';
    if(!currentRoom) return;
    // If a file is selected, perform atomic upload using messages_with_file endpoint with progress
    if(fileSelected){
      const file = fileEl.files[0];
      const fd = new FormData();
      fd.append('text', text);
      if(replyTo) fd.append('reply_to', replyTo);
      fd.append('file', file, file.name);
      // per-attachment progress element
      const progressWrap = document.createElement('div'); progressWrap.className='attachment-progress';
      progressWrap.textContent = `Uploading ${file.name}: `;
      const prog = document.createElement('progress'); prog.max = 100; prog.value = 0; progressWrap.appendChild(prog);
      messagesEl.appendChild(progressWrap);
      const url = isDialog ? `/dialogs/${currentRoom.id}/messages_with_file` : `/rooms/${currentRoom.id}/messages_with_file`;
      const xhr = new XMLHttpRequest();
      xhr.open('POST', url);
      xhr.onload = function(){
        try{
          const json = JSON.parse(xhr.responseText);
          if(json && json.message){
            // construct full message object including files
            const fullMsg = Object.assign({}, json.message);
            if(json.file) fullMsg.files = [json.file];
            const el2 = appendMessage(fullMsg);
            // replace placeholder with the real message element
            messagesEl.replaceChild(el2, placeholder);
            latestTimestamp = json.message.created_at || latestTimestamp;
          }
        }catch(e){ console.error('parse response', e); }
        progressWrap.remove();
      };
      xhr.onerror = function(){ alert('Upload failed'); progressWrap.remove(); };
      // on network error: mark placeholder as failed and show retry/cancel
      xhr.addEventListener('error', ()=>{
        if(placeholder){
          placeholder.classList.add('failed');
          status.textContent = 'Failed';
        }
      });
      xhr.upload.onprogress = function(ev){ if(ev.lengthComputable){ const pct = Math.round((ev.loaded/ev.total)*100); prog.value = pct; } };
      xhr.send(fd);
      // wire retry / cancel handlers
      retryBtn.addEventListener('click', ()=>{
        // clear failed state and re-send
        if(placeholder) placeholder.classList.remove('failed');
        status.textContent = '';
        // re-send by triggering the same XHR logic again (simple approach: reload page to re-run flow)
        // better approach: encapsulate send logic in a function; for now, re-submit by programmatically clicking send
        composer.querySelector('button[type=submit]').click();
      });
      cancelBtn.addEventListener('click', ()=>{ if(placeholder && placeholder.parentNode) placeholder.parentNode.removeChild(placeholder); });
    } else {
      if(isDialog){
        fetch(`/dialogs/${currentRoom.id}/messages`, {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(payload)})
          .then(r=>r.json())
          .then(json=>{
            if(json && json.message){
              const fullMsg = Object.assign({}, json.message);
              const el2 = appendMessage(fullMsg);
              messagesEl.replaceChild(el2, placeholder);
              latestTimestamp = json.message.created_at || latestTimestamp;
              if(autoscroll) messagesEl.scrollTop = messagesEl.scrollHeight;
            }
          }).catch(err=>{ console.error('send dialog message failed', err); // remove placeholder on error
            if(placeholder && placeholder.parentNode) placeholder.parentNode.removeChild(placeholder);
          });
      } else {
        fetch(`/rooms/${currentRoom.id}/messages`, {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(payload)})
          .then(r=>r.json())
          .then(json=>{
            if(json && json.message){
              const fullMsg = Object.assign({}, json.message);
              const el2 = appendMessage(fullMsg);
              messagesEl.replaceChild(el2, placeholder);
              latestTimestamp = json.message.created_at || latestTimestamp;
              if(autoscroll) messagesEl.scrollTop = messagesEl.scrollHeight;
            }
          }).catch(err=>{ console.error('send room message failed', err); if(placeholder && placeholder.parentNode) placeholder.parentNode.removeChild(placeholder); });
      }
    }
    // clear reply state
    const replyPreviewEl = document.getElementById('reply-preview');
    if(replyPreviewEl) replyPreviewEl.style.display = 'none';
    delete composerEl.dataset.replyTo;
  });

  // handle Shift+Enter for newline in textarea
  input.addEventListener('keydown', (ev)=>{
    if(ev.key === 'Enter' && ev.shiftKey){
      const start = input.selectionStart;
      const end = input.selectionEnd;
      const val = input.value;
      input.value = val.substring(0, start) + '\n' + val.substring(end);
      input.selectionStart = input.selectionEnd = start + 1;
      ev.preventDefault();
    }
  });

  // inline emoji picker
  const emojiBtn = document.getElementById('emoji-btn');
  const emojiPicker = document.getElementById('emoji-picker');
  const emojis = ['😀','😁','😂','🤣','😊','😍','😎','😅','🙂','😉','🙃','😘','🤔','😴','😡','👍','👎','🙏','🎉','🔥','💯','🚀','🌟','🍕','☕️','📎','📷','🖼️','🎵','✅','❌','➕','➖'];
  function buildEmojiPicker(){
    if(!emojiPicker) return;
    emojiPicker.innerHTML = '';
    const grid = document.createElement('div'); grid.className='emoji-grid';
    emojis.forEach(e=>{
      const btn = document.createElement('button'); btn.type='button'; btn.textContent = e;
      btn.addEventListener('click', ()=>{
        const pos = input.selectionStart || input.value.length;
        input.value = input.value.slice(0,pos) + e + input.value.slice(pos);
        input.focus();
        emojiPicker.style.display = 'none';
      });
      grid.appendChild(btn);
    });
    emojiPicker.appendChild(grid);
  }
  buildEmojiPicker();
  if(emojiBtn){
    emojiBtn.addEventListener('click', (ev)=>{
      ev.stopPropagation();
      if(!emojiPicker) return;
      emojiPicker.style.display = emojiPicker.style.display === 'block' ? 'none' : 'block';
    });
  }
  // hide picker when clicking elsewhere
  document.addEventListener('click', (ev)=>{ if(emojiPicker) emojiPicker.style.display='none'; });

  // file attachment handling with upload guard and spinner
  const fileInput = document.getElementById('file-input');
  let uploading = false;
  const uploadingIndicator = document.getElementById('uploading-indicator');
  // file selection preview: do not auto-upload; user will send with composer submit which uses atomic endpoint
  if(fileInput){
    const selectedWrap = document.createElement('div'); selectedWrap.className='selected-file';
    fileInput.parentNode.insertBefore(selectedWrap, fileInput.nextSibling);
    fileInput.addEventListener('change', ()=>{
      selectedWrap.innerHTML = '';
      if(!fileInput.files || fileInput.files.length === 0) return;
      const file = fileInput.files[0];
      const info = document.createElement('div'); info.textContent = `Selected: ${file.name} `;
      const remove = document.createElement('button'); remove.type='button'; remove.textContent='Remove';
      remove.addEventListener('click', ()=>{ fileInput.value=''; selectedWrap.innerHTML=''; });
      info.appendChild(remove);
      selectedWrap.appendChild(info);
    });
  }

  // reply cancel
  const replyCancel = document.getElementById('reply-cancel');
  if(replyCancel){
    replyCancel.addEventListener('click', ()=>{
      const rp = document.getElementById('reply-preview'); if(rp) rp.style.display='none';
      const composerEl = document.getElementById('composer'); delete composerEl.dataset.replyTo;
    });
  }

  // helper: basic fetch wrapper
  async function fetchJSON(url, opts){
    try{
      const r = await fetch(url, opts);
      if(!r.ok){
        console.warn('fetch failed', url, r.status);
        return null;
      }
      return await r.json();
    }catch(e){
      console.error('fetch error', url, e);
      return null;
    }
  }

  async function loadRooms(){
    const data = await fetchJSON('/rooms');
    if(data && data.rooms){
      rooms = data.rooms;
      renderRooms();
      if(rooms.length) selectRoom(rooms[0]);
    }
  }

  async function loadContacts(){
    const data = await fetchJSON('/friends');
    if(data && data.friends){
      contacts = data.friends.map(f=>({id: f.id, name: f.username || f.email || ('user'+f.id)}));
      renderContacts();
    }
  }

  async function loadRoomMembers(roomId){
    const data = await fetchJSON(`/rooms/${roomId}`);
    if(!data || !data.room) return renderMembers([]);
    const memberIds = data.room.members || [];
    if(memberIds.length === 0) return renderMembers([]);
    // batch presence and user lookup
    const idsParam = memberIds.join(',');
    const [presResp, usersResp] = await Promise.all([
      fetchJSON(`/presence?ids=${encodeURIComponent(idsParam)}`),
      fetchJSON(`/users?ids=${encodeURIComponent(idsParam)}`)
    ]);
    const statuses = (presResp && presResp.statuses) || {};
    const users = (usersResp && usersResp.users) || [];
    const nameById = {};
    users.forEach(u => { nameById[String(u.id)] = u.username || u.email || ('user' + u.id); });
    const members = memberIds.map(id => ({ name: nameById[String(id)] || ('user ' + id), online: statuses[String(id)] === 'online' }));
    renderMembers(members);
  }

  async function loadRoomMessages(roomId, opts){
    opts = opts || {};
    const before = opts.before ? `?before=${encodeURIComponent(opts.before)}` : '';
    const data = await fetchJSON(`/rooms/${roomId}/messages${before}`);
    if(!data || !data.messages) return;
    // if prepend: preserve scroll position
    if(opts.prepend){
      const oldScrollHeight = messagesEl.scrollHeight;
      const frag = document.createDocumentFragment();
      data.messages.forEach(m=>{
        // pass the full message object so appendMessage can access id, reply, files, etc.
        const el = appendMessage(m);
        frag.insertBefore(el, frag.firstChild);
        earliestTimestamp = earliestTimestamp ? Math.min(earliestTimestamp, m.created_at) : m.created_at;
      });
      messagesEl.insertBefore(frag, messagesEl.firstChild);
      // restore scroll position to where the user was
      const newScrollHeight = messagesEl.scrollHeight;
      messagesEl.scrollTop = newScrollHeight - oldScrollHeight + messagesEl.scrollTop;
    } else {
      messagesEl.innerHTML = '';
      data.messages.forEach(m=>{
        const el = appendMessage(m);
        messagesEl.appendChild(el);
        earliestTimestamp = earliestTimestamp ? Math.min(earliestTimestamp, m.created_at) : m.created_at;
        latestTimestamp = m.created_at || latestTimestamp;
      });
      // initial load: scroll to bottom
      messagesEl.scrollTop = messagesEl.scrollHeight;
      autoscroll = true;
    }
  }

  async function loadDialogMessages(otherId, opts){
    opts = opts || {};
    const before = opts.before ? `?before=${encodeURIComponent(opts.before)}` : '';
    const data = await fetchJSON(`/dialogs/${otherId}/messages${before}`);
    if(!data || !data.messages) return;
    if(opts.prepend){
      const oldScrollHeight = messagesEl.scrollHeight;
      const frag = document.createDocumentFragment();
      data.messages.forEach(m=>{
        const el = appendMessage(m);
        frag.insertBefore(el, frag.firstChild);
        earliestTimestamp = earliestTimestamp ? Math.min(earliestTimestamp, m.created_at) : m.created_at;
      });
      messagesEl.insertBefore(frag, messagesEl.firstChild);
      const newScrollHeight = messagesEl.scrollHeight;
      messagesEl.scrollTop = newScrollHeight - oldScrollHeight + messagesEl.scrollTop;
    } else {
      messagesEl.innerHTML = '';
      data.messages.forEach(m=>{
        const el = appendMessage(m);
        messagesEl.appendChild(el);
        earliestTimestamp = earliestTimestamp ? Math.min(earliestTimestamp, m.created_at) : m.created_at;
        latestTimestamp = m.created_at || latestTimestamp;
      });
      messagesEl.scrollTop = messagesEl.scrollHeight;
      autoscroll = true;
    }
  }

  // bootstrap auth via /refresh; if unauthenticated redirect to login page
  async function bootstrap(){
    const r = await fetch('/refresh', {method: 'POST', credentials: 'include'}).catch(()=>null);
    if(!r || r.status === 401){
      // redirect to the hosted login page which will set cookie on success
      location.href = '/static/login.html';
      return;
    }
    // ready: load data
    await loadRooms();
    await loadContacts();
  }

  bootstrap();

  roomsToggle.addEventListener('click', ()=>{
    roomsSection.classList.toggle('compacted');
  });
});
