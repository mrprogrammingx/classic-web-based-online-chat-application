// Messages UI wiring (autoscroll & infinite scroll)
(function(){
  function initMessagesUi(){
    try{
      const messagesEl = document.getElementById('messages');
      if(!messagesEl) return;
      // autoscroll only when appropriate:
      // - on initial load
      // - when the user is already near the bottom
      let initialLoad = true;
      let userNearBottom = true;
      const BOTTOM_THRESHOLD = 50; // px from bottom

      function updateUserNearBottom(){
        try{
          const dist = messagesEl.scrollHeight - messagesEl.scrollTop - messagesEl.clientHeight;
          userNearBottom = dist < BOTTOM_THRESHOLD;
          try{ window.autoscroll = Boolean(userNearBottom); }catch(e){}
        }catch(e){ userNearBottom = false; }
      }

      // make a best-effort initial scroll to bottom once
      try{ messagesEl.scrollTop = messagesEl.scrollHeight; }catch(e){}
      // after a short delay consider initial load done
      setTimeout(()=>{ initialLoad = false; updateUserNearBottom(); }, 250);

      // track user scroll position to determine whether to auto-scroll
      messagesEl.addEventListener('scroll', ()=>{ updateUserNearBottom(); }, { passive: true });

      const obs = new MutationObserver(()=>{
        try{
          // Determine whether to scroll BEFORE reading the new scroll metrics.
          // `userNearBottom` was set by the most recent scroll event (before the
          // DOM mutation) so it reflects the user's intent accurately.
          const shouldScroll = initialLoad || userNearBottom;
          if(shouldScroll){
            messagesEl.scrollTop = messagesEl.scrollHeight;
          }
          // Update the flag after scrolling so subsequent mutations use the
          // correct baseline.
          updateUserNearBottom();
        }catch(e){}
      });
      // start observing on next tick so immediate scroll events after init are captured
      setTimeout(()=>{ try{ obs.observe(messagesEl, {childList:true, subtree:true}); }catch(e){} }, 0);
    }catch(e){}
  }
  try{ window.initMessagesUi = initMessagesUi; }catch(e){}
})();
