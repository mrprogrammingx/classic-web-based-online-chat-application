// Messages UI wiring (autoscroll and infinite scroll handler)
(function(){
  function initMessagesUi(){
    try{ window.autoscroll = true; }catch(e){}
    function userIsAtBottom(){
      const threshold = 40; // px
      try{ return window.messagesEl.scrollHeight - window.messagesEl.scrollTop - window.messagesEl.clientHeight < threshold; }catch(e){ return true; }
    }
    try{ window.messagesEl.addEventListener('scroll', ()=>{
      window.autoscroll = userIsAtBottom();
      try{
        if(window.messagesEl.scrollTop < 50 && window.currentRoom){
          if(window.isDialog){
            if(typeof window.loadDialogMessages === 'function') window.loadDialogMessages(window.currentRoom.id, {before: window.earliestTimestamp, prepend: true});
          } else {
            if(typeof window.loadRoomMessages === 'function') window.loadRoomMessages(window.currentRoom.id, {before: window.earliestTimestamp, prepend: true});
          }
        }
      }catch(e){}
    }); }catch(e){}
  }

  try{ window.initMessagesUi = initMessagesUi; }catch(e){}
})();
