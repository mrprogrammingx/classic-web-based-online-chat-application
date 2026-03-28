// header-loader.js
// Minimal, clean header loader: injects a tiny synchronous skeleton so other
// scripts can use known DOM IDs, loads a short site-config (300ms timeout),
// then attempts to fetch and inject /static/header/header.html (fallback
// to /header/header.html). Any inline scripts found in the fragment are
// executed.

(async function(){
  'use strict';

  function escapeHtml(s){ return String(s||'').replace(/[&<>'\"]/g, c=>({ '&':'&amp;','<':'&lt;','>':'&gt;',"'":"&#39;", '"':'&quot;' })[c]); }

  const ph = document.getElementById('shared-header-placeholder');
  if(!ph) return;
  const cust = document.getElementById('header-custom');

  const defaults = {
    brand: 'Chat Demo',
    mainButtonText: 'Chat',
    mainHref: '/static/chat/index.html',
    homeHref: '/static/home.html',
    adminHref: '/static/admin/index.html',
    adminButtonText: 'Admin'
  };

  async function loadSiteConfig(timeoutMs = 300){
    try{
      const controller = new AbortController();
      const id = setTimeout(()=>controller.abort(), timeoutMs);
      const res = await fetch('/static/site-config.json', { signal: controller.signal });
      clearTimeout(id);
      if(!res.ok) return {};
      return await res.json().catch(()=> ({}));
    }catch(e){ return {}; }
  }

  function injectSkeleton(cfg){
    ph.innerHTML = (
      '<header class="topmenu">' +
        '<div class="brand">' + escapeHtml(cfg.brand) + '</div>' +
        '<nav class="topnav"><div class="nav-left"></div>' +
        '<div id="user-info" class="user-info" aria-live="polite"></div>' +
        '<div id="notifications" class="nav-notifications">' +
          '<button id="unread-total" class="unread-total" title="Unread notifications" aria-live="polite" aria-atomic="true">' +
            '<span class="unread-icon">📨</span><span class="unread-count">0</span>' +
          '</button>' +
          '<span id="unread-live" class="sr-only" aria-live="polite"></span>' +
        '</div></nav>' +
      '</header>'
    );
  }

  async function fetchHeaderFragment(){
    const candidates = ['/static/header/header.html', '/header/header.html'];
    for(const url of candidates){
      try{
        const res = await fetch(url);
        if(res && res.ok) return await res.text();
      }catch(e){ /* ignore and try next */ }
    }
    return null;
  }

  function executeScripts(container){
    const scripts = container.querySelectorAll('script');
    for(const s of scripts){
      try{
        const ns = document.createElement('script');
        if(s.src){ ns.src = s.src; ns.async = false; }
        else { ns.textContent = s.textContent || s.innerText || ''; }
        if(s.type) ns.type = s.type;
        document.head.appendChild(ns);
      }catch(e){ console.warn('header-loader: script exec failed', e); }
      try{ s.parentNode && s.parentNode.removeChild(s); }catch(e){}
    }
  }

  function applyCustomizations(cfg){
    try{
      const brandEl = ph.querySelector('.brand'); if(brandEl && cfg.brand) brandEl.textContent = cfg.brand;
      // Prefer explicit chat/main button elements. Do not overwrite the 'Home' label.
      const chatBtn = ph.querySelector('#btn-chat') || ph.querySelector('#btn-back-to-chat');
      if(chatBtn){
        if(cfg.mainButtonText) chatBtn.textContent = cfg.mainButtonText;
        if(cfg.mainHref) chatBtn.href = cfg.mainHref;
      }
      // Ensure the home button uses the canonical href but keep its label (usually 'Home')
      const homeBtn = ph.querySelector('#btn-home');
      if(homeBtn && cfg.homeHref) homeBtn.href = cfg.homeHref;
      const adminBtn = ph.querySelector('#admin-open'); if(adminBtn && cfg.adminButtonText) adminBtn.textContent = cfg.adminButtonText;
    }catch(e){ console.warn('header-loader: applyCustomizations failed', e); }
  }

  function injectFallbackHome(cfg){
    try{
      const left = ph.querySelector('.nav-left');
      if(left) left.innerHTML = '<a href="' + escapeHtml(cfg.homeHref || '/static/home.html') + '" class="btn btn-secondary" id="btn-home">Home</a>';
    }catch(e){}
  }

  const siteCfg = await loadSiteConfig(300);
  const cfg = Object.assign({}, defaults, siteCfg || {});
  if(cust && cust.dataset){
    if(cust.dataset.brand) cfg.brand = cust.dataset.brand;
    if(cust.dataset.mainButtonText) cfg.mainButtonText = cust.dataset.mainButtonText;
    if(cust.dataset.mainButtonHref) cfg.mainHref = cust.dataset.mainButtonHref;
    if(cust.dataset.adminButtonText) cfg.adminButtonText = cust.dataset.adminButtonText;
    if(cust.dataset.adminButtonHref) cfg.adminHref = cust.dataset.adminButtonHref;
  }

  try{ window.SITE_CONFIG = Object.assign({}, cfg); }catch(e){}
  injectSkeleton(cfg);

  try{
    const fragHtml = await fetchHeaderFragment();
    if(!fragHtml){
      injectFallbackHome(cfg);
      try{ window.dispatchEvent(new Event('shared-header-loaded')); }catch(e){}
      return;
    }
    const container = document.createElement('div'); container.innerHTML = fragHtml;
    ph.innerHTML = '';
    while(container.firstChild) ph.appendChild(container.firstChild);
    executeScripts(ph);
    applyCustomizations(cfg);
    try{ window.dispatchEvent(new Event('shared-header-loaded')); }catch(e){}
  }catch(err){
    console.warn('header-loader: failed to load/inject header fragment', err);
    injectFallbackHome(cfg);
    try{ window.dispatchEvent(new Event('shared-header-loaded')); }catch(e){}
  }

})();
