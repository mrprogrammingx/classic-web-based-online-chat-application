// admin-page.js
// If the shared admin UI is available (openAdminPanel), render it into the
// #admin-content container. Otherwise fall back to an inline implementation.
(function(){
  'use strict';
  async function initAdminUI(){
    if(initAdminUI._init) return; initAdminUI._init = true;
    const el = document.getElementById('admin-content'); if(!el) return;
    if(typeof window.openAdminPanel === 'function'){
      window.openAdminPanel(el);
      return;
    }
    // fallback: simple placeholder until openAdminPanel is available or page reload
    el.innerHTML = '<div class="admin-empty">Admin UI is loading…</div>';
  }

  window.addEventListener('shared-header-loaded', initAdminUI);
  document.addEventListener('DOMContentLoaded', initAdminUI);
})();
