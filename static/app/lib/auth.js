// Auth UI helpers (logout binding)
(function(){
  function _bindLogout(el){
    if(!el) return;
    el.addEventListener('click', function(ev){
      ev.preventDefault();
      var href = el.getAttribute('href') || el.dataset.href || '/logout';
      fetch(href, { method: 'POST', credentials: 'same-origin' })
        .then(function(){ window.location = '/'; })
        .catch(function(){ window.location = '/'; });
    });
  }

  function initAuthUi(root=document){
    root = root || document;
    var selectors = ['[data-action="logout"]', '#btn-logout', '#btn-logout-inline'];
    selectors.forEach(function(sel){ var el = root.querySelector(sel); if(el) _bindLogout(el); });
  }
  window.initAuthUi = initAuthUi;
})();
