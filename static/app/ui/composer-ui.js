// Composer small UI helpers (reply cancel, attachment clear)
(function(){
  function initComposerUi(root){
    try{
      const replyCancel = document.getElementById('reply-cancel');
      if(replyCancel){ replyCancel.addEventListener('click', ()=>{ try{ document.getElementById('reply-preview').style.display='none'; }catch(e){} }); }
      // click-on-message to set reply preview
      try{
        document.addEventListener('click', (ev)=>{
          try{
            const msg = ev.target && ev.target.closest && ev.target.closest('.message');
            if(!msg) return;
            // find the original text in the clicked message
            const textEl = msg.querySelector('.body');
            const author = msg.querySelector('.meta strong');
            const mid = msg.dataset && (msg.dataset.id || msg.getAttribute('data-id'));
            const replyPreview = document.getElementById('reply-preview');
            if(replyPreview && textEl){
              try{ document.getElementById('reply-to-author').textContent = (author && author.textContent) || '' }catch(e){}
              try{ document.getElementById('reply-to-text').textContent = textEl.textContent || ''; }catch(e){}
              try{ replyPreview.style.display = 'flex'; }catch(e){}
              try{ const composer = document.getElementById('composer'); if(composer && mid) composer.dataset.replyTo = mid; }catch(e){}
            }
          }catch(e){}
        });
      }catch(e){}
    }catch(e){}
  }
  try{ window.initComposerUi = initComposerUi; }catch(e){}
})();
