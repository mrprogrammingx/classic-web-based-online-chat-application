// Composer small UI helpers (reply cancel, attachment clear)
(function(){
  function initComposerUi(root){
    try{
      const replyCancel = document.getElementById('reply-cancel');
      if(replyCancel){ replyCancel.addEventListener('click', ()=>{ try{ document.getElementById('reply-preview').style.display='none'; }catch(e){} }); }
    }catch(e){}
  }
  try{ window.initComposerUi = initComposerUi; }catch(e){}
})();
