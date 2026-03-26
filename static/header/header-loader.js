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
  // default values (will be overridden by site-config.json or data attributes)
  const defaults = {
    brand: 'Chat Demo',
    mainButtonText: 'Chat',
    mainHref: '/static/chat/index.html',
    adminHref: '/static/admin/index.html',
    adminButtonText: 'Admin'
  };

  // helper to fetch site config with a short timeout and fall back to defaults
  function fetchSiteConfig(timeoutMs){
    const controller = new AbortController();
    const id = setTimeout(()=>controller.abort(), timeoutMs||300);
    return fetch('/static/site-config.json', { signal: controller.signal }).then(r=>{ clearTimeout(id); if(!r.ok) throw new Error('bad response'); return r.json(); }).catch(()=> ({}));
  }

  // fetch site config (short timeout) then proceed to load header fragment
  fetchSiteConfig(300).then(siteCfg=>{
    const cfg = Object.assign({}, defaults, siteCfg || {});
    // override with data- attributes if present
    if(cust && cust.dataset){
      if(cust.dataset.brand) cfg.brand = cust.dataset.brand;
      if(cust.dataset.mainButtonText) cfg.mainButtonText = cust.dataset.mainButtonText;
      if(cust.dataset.mainButtonHref) cfg.mainHref = cust.dataset.mainButtonHref;
      if(cust.dataset.adminButtonText) cfg.adminButtonText = cust.dataset.adminButtonText;
      if(cust.dataset.adminButtonHref) cfg.adminHref = cust.dataset.adminButtonHref;
    }

  // expose resolved site config for other scripts to consume (global read-only)
  try{ window.SITE_CONFIG = Object.assign({}, cfg); }catch(e){}

  // insert small skeleton immediately so early scripts can find the DOM ids
    ph.innerHTML = `<header class="topmenu"><div class="brand">${escapeHtml(cfg.brand)}</div><nav class="topnav"><div class="nav-left"><a href="${escapeHtml(cfg.mainHref)}" class="btn btn-secondary" id="btn-back-to-chat">${escapeHtml(cfg.mainButtonText)}</a></div><div id="user-info" class="user-info" aria-live="polite"></div><div id="notifications" class="nav-notifications"><button id="unread-total" class="unread-total" title="Unread notifications" aria-live="polite" aria-atomic="true"><span class="unread-icon">📨</span><span class="unread-count">0</span></button><span id="unread-live" class="sr-only" aria-live="polite"></span></div></nav></header>`;

  // header fragment may be served from either /header/header.html or
  // /static/header/header.html depending on how the server is configured.
  // Try the shorter path first; if the response is not OK (404), fetch the
  // static path as a fallback.
  return fetch('/header/header.html').then(r=>{ if(r && r.ok) return r; return fetch('/static/header/header.html'); }).catch(()=> fetch('/static/header/header.html'));
  }).then(r=>r.text()).then(html=>{
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

      // apply per-page customizations from #header-custom and resolved cfg
      if(cust || typeof cfg !== 'undefined'){
        try{
          const b = ph.querySelector('.brand'); if(b && cfg.brand) b.textContent = cfg.brand;
          const mb = ph.querySelector('#btn-back-to-chat') || ph.querySelector('#btn-home');
          if(mb && cfg.mainButtonText) mb.textContent = cfg.mainButtonText;
          if(mb && cfg.mainHref) mb.href = cfg.mainHref;
          const ab = ph.querySelector('#admin-open'); if(ab && cfg.adminButtonText) ab.textContent = cfg.adminButtonText;
          // if page specifically requests admin button via data attr, convert chat button into admin link
          if(cust && cust.dataset && cust.dataset.adminButtonText){
            const chatBtn = ph.querySelector('#btn-chat') || ph.querySelector('#btn-back-to-chat');
            if(chatBtn){ chatBtn.id = 'btn-admin-link'; chatBtn.textContent = cfg.adminButtonText || 'Admin'; chatBtn.href = cfg.adminHref || '/static/admin/index.html'; chatBtn.classList.remove('btn-secondary'); chatBtn.classList.add('btn'); }
          }
        }catch(e){ console.warn('header-loader: apply customization failed', e); }
      }

    }catch(e){ console.warn('header-loader: failed to inject header', e); }
    try{ window.dispatchEvent(new Event('shared-header-loaded')); }catch(e){}
  }).catch(err=>{ console.warn('header-loader: failed to load shared header', err); });
})();
