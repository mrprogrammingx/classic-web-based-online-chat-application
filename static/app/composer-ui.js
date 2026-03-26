// Composer UI helpers: reply-cancel, preview clearing
(function(){
  function initComposerUi(root){
    root = root || document;
    var cancel = root.querySelector('.reply-cancel') || root.querySelector('#reply-cancel');
    if(cancel){
      cancel.addEventListener('click', function(ev){
        ev.preventDefault();
        var composer = root.querySelector('#composer');
        if(!composer) return;
        var replyTo = composer.querySelector('[name="reply_to"]'); if(replyTo) replyTo.value = '';
        var preview = composer.querySelector('.reply-preview');
        if(preview) preview.style.display = 'none';
        var previewText = composer.querySelector('#reply-to-text') || composer.querySelector('.reply-preview .text');
        if(previewText) previewText.textContent = '';
        try{ delete composer.dataset.replyTo; }catch(e){}
      });
    }

    // clear file preview on clear button if present
    var clearAttach = root.querySelector('.attachment-clear');
    if(clearAttach){
      clearAttach.addEventListener('click', function(ev){
        ev.preventDefault();
        var fileInput = root.querySelector('#composer input[type=file]');
        if(fileInput){ fileInput.value = null; }
        var preview = root.querySelector('.attachment-preview');
        if(preview) preview.innerHTML = '';
      });
    }
  }
  window.initComposerUi = initComposerUi;
})();
