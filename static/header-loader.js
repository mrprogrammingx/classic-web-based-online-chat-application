// header-loader.js
// Centralized header loading: inject a small skeleton, fetch /static/header.html,
// replace the skeleton with the canonical fragment, execute any scripts found
// in the fragment, apply per-page customizations (from #header-custom), and
// dispatch `shared-header-loaded`.
(function(){
  'use strict';
  function escapeHtml(s){ return String(s||'').replace(/[&<>'"]/g, c=>({ '&':'&amp;','<':'&lt;','>':'&gt;',"'":"&#39;", '"':'&quot;' })[c]); }
  const ph = document.getElementById('shared-header-placeholder'); if(!ph) return;
  const cust = document.getElementById('header-custom');
  const brand = cust && cust.dataset && cust.dataset.brand ? cust.dataset.brand : 'Chat Demo';
  const mainText = cust && cust.dataset && cust.dataset.mainButtonText ? cust.dataset.mainButtonText : 'Chat';
  const mainHref = cust && cust.dataset && cust.dataset.mainButtonHref ? cust.dataset.mainButtonHref : '/static/chat.html';

  // insert small skeleton immediately so early scripts can find the DOM ids
  ph.innerHTML = `<header class="topmenu"><div class="brand">${escapeHtml(brand)}</div><nav class="topnav"><div class="nav-left"><a href="${escapeHtml(mainHref)}" class="btn btn-secondary" id="btn-back-to-chat">${escapeHtml(mainText)}</a></div><div id="user-info" class="user-info" aria-live="polite"></div><div id="notifications" class="nav-notifications"><button id="unread-total" class="unread-total" title="Unread notifications" aria-live="polite" aria-atomic="true"><span class="unread-icon">📨</span><span class="unread-count">0</span></button><span id="unread-live" class="sr-only" aria-live="polite"></span></div></nav></header>`;

  fetch('/static/header.html').then(r=>r.text()).then(html=>{
    try{
      // parse fetched fragment into a temp container
      const container = document.createElement('div'); container.innerHTML = html;
      // replace skeleton with fetched nodes
      ph.innerHTML = '';
      while(container.firstChild) ph.appendChild(container.firstChild);

      // execute any <script> tags found inside the fragment (re-create them on head)
      const scripts = ph.querySelectorAll('script');
      scripts.forEach(s => {
        try{
          const ns = document.createElement('script');
          if(s.src){ ns.src = s.src; ns.async = false; }
          else { ns.textContent = s.textContent || s.innerText || ''; }
          if(s.type) ns.type = s.type;
          document.head.appendChild(ns);
        }catch(e){ console.warn('header-loader: failed to run script', e); }
        try{ s.parentNode && s.parentNode.removeChild(s); }catch(e){}
      });

      // apply per-page customizations from #header-custom
      if(cust){
        try{
          const b = ph.querySelector('.brand'); if(b && cust.dataset.brand) b.textContent = cust.dataset.brand;
          const mb = ph.querySelector('#btn-back-to-chat') || ph.querySelector('#btn-home');
          if(mb && cust.dataset.mainButtonText) mb.textContent = cust.dataset.mainButtonText;
          if(mb && cust.dataset.mainButtonHref) mb.href = cust.dataset.mainButtonHref;
          const ab = ph.querySelector('#admin-open'); if(ab && cust.dataset.adminButtonText) ab.textContent = cust.dataset.adminButtonText;
          if(cust.dataset && cust.dataset.adminButtonText){
            const chatBtn = ph.querySelector('#btn-chat') || ph.querySelector('#btn-back-to-chat');
            if(chatBtn){ chatBtn.id = 'btn-admin-link'; chatBtn.textContent = 'Admin'; chatBtn.href = '/static/admin.html'; chatBtn.classList.remove('btn-secondary'); chatBtn.classList.add('btn'); }
          }
        }catch(e){ console.warn('header-loader: apply customization failed', e); }
      }

    }catch(e){ console.warn('header-loader: failed to inject header', e); }
    try{ window.dispatchEvent(new Event('shared-header-loaded')); }catch(e){}
  }).catch(err=>{ console.warn('header-loader: failed to load shared header', err); });
})();
