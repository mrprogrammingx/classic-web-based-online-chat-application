// Messages UI wiring (autoscroll & infinite scroll)
(function(){
  function initMessagesUi(){
    try{
      const messagesEl = document.getElementById('messages');
      if(!messagesEl) return;
      // simple autoscroll on new messages
      const obs = new MutationObserver(()=>{ try{ messagesEl.scrollTop = messagesEl.scrollHeight; }catch(e){} });
      obs.observe(messagesEl, {childList:true, subtree:true});
    }catch(e){}
  }
  try{ window.initMessagesUi = initMessagesUi; }catch(e){}
})();
