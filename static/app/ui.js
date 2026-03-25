// Centralized UI helpers (modals & toasts) extracted from app.js
(function(){
  // small HTML-escape helper
  function escapeHtml(str){ return String(str).replace(/[&<>'"]/g, (s)=>({ '&':'&amp;', '<':'&lt;', '>':'&gt;', "'":"&#39;", '"':'&quot;' }[s])); }

  // Modal utility: returns a Promise<boolean>
  function showModal(opts){
    let root = document.getElementById('modal-root');
    if(!root){ try{ root = document.createElement('div'); root.id = 'modal-root'; document.body.appendChild(root); }catch(e){} }
    if(!root) { return Promise.resolve(false); }
    return new Promise((resolve)=>{
      root.innerHTML = '';
      const previouslyFocused = document.activeElement;
      const backdrop = document.createElement('div'); backdrop.className = 'modal-backdrop';
      const box = document.createElement('div'); box.className = 'modal-box';
      const title = document.createElement('h3');
      const titleId = 'modal-title-' + Math.random().toString(36).slice(2,9);
      title.id = titleId;
      title.textContent = opts.title || 'Confirm';
      const body = document.createElement('div'); body.className = 'modal-body'; body.innerHTML = `${escapeHtml(opts.body || '')}`;
      const actions = document.createElement('div'); actions.className = 'modal-actions';
      const cancel = document.createElement('button'); cancel.type='button'; cancel.textContent = opts.cancelText || 'Cancel';
      const confirm = document.createElement('button'); confirm.type='button'; confirm.textContent = opts.confirmText || 'OK'; confirm.className='confirm';
      actions.appendChild(cancel); actions.appendChild(confirm);
      box.appendChild(title); box.appendChild(body); box.appendChild(actions);
      box.setAttribute('role', 'dialog'); box.setAttribute('aria-modal', 'true'); box.setAttribute('aria-labelledby', titleId);
      backdrop.appendChild(box); root.appendChild(backdrop);

      // focus management
      const focusable = [confirm, cancel];
      let focusIndex = 0;
      function focusFirst(){ focusIndex = 0; focusable[focusIndex].focus(); }
      function handleKey(e){
        if(e.key === 'Escape'){ e.preventDefault(); cleanup(); resolve(false); }
        else if(e.key === 'Tab'){ e.preventDefault(); if(e.shiftKey) focusIndex = (focusIndex - 1 + focusable.length) % focusable.length; else focusIndex = (focusIndex + 1) % focusable.length; focusable[focusIndex].focus(); }
      }

      function cleanup(){ root.innerHTML = ''; document.removeEventListener('keydown', handleKey); try{ if(previouslyFocused && previouslyFocused.focus) previouslyFocused.focus(); }catch(e){} }

      cancel.addEventListener('click', ()=>{ cleanup(); resolve(false); });
      backdrop.addEventListener('click', (e)=>{ if(e.target === backdrop){ cleanup(); resolve(false); } });
      confirm.addEventListener('click', ()=>{ cleanup(); resolve(true); });

      document.addEventListener('keydown', handleKey);
      setTimeout(()=>{ try{ confirm.focus(); }catch(e){} }, 0);
    });
  }

  // Toast utility
  function showToast(msg, type='success', timeout=3000){
    let root = document.getElementById('toast-root');
    if(!root){ try{ root = document.createElement('div'); root.id = 'toast-root'; document.body.appendChild(root); }catch(e){ console.warn('toast fallback:', msg); return; } }
    if(!root.querySelector('.toast-container')){ const cont = document.createElement('div'); cont.className = 'toast-container'; cont.setAttribute('role', 'status'); cont.setAttribute('aria-live', 'polite'); cont.setAttribute('aria-atomic', 'false'); root.appendChild(cont); }
    const cont = root.querySelector('.toast-container'); const t = document.createElement('div'); t.className = 'toast ' + (type==='success'? 'success': (type==='error'? 'error':'')); t.textContent = msg; t.setAttribute('role','status'); cont.appendChild(t);
    setTimeout(()=>{ t.style.opacity='0'; t.style.transform='translateY(8px)'; setTimeout(()=>t.remove(),240); }, timeout);
  }

  try{ window.showModal = showModal; window.showToast = showToast; }catch(e){}
})();