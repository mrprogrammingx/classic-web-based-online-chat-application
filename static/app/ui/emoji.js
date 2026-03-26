// Emoji picker setup (moved out of app.js)
(function(){
  function buildEmojiPicker(){
    const emojiPicker = document.getElementById('emoji-picker');
    const input = document.getElementById('message-input');
    const emojiBtn = document.getElementById('emoji-btn');
    const emojis = ['😀','😁','😂','🤣','😊','😍','😎','😅','🙂','😉','🙃','😘','🤔','😴','😡','👍','👎','🙏','🎉','🔥','💯','🚀','🌟','🍕','☕️','📎','📷','🖼️','🎵','✅','❌','➕','➖'];
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

    if(emojiBtn){
      emojiBtn.addEventListener('click', (ev)=>{
        ev.stopPropagation();
        if(!emojiPicker) return;
        emojiPicker.style.display = emojiPicker.style.display === 'block' ? 'none' : 'block';
      });
    }

    // hide picker when clicking elsewhere
    document.addEventListener('click', ()=>{ if(emojiPicker) emojiPicker.style.display='none'; });
  }

  try{ window.initEmojiPicker = buildEmojiPicker; }catch(e){}
})();
