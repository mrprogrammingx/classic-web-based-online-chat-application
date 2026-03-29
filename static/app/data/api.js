// Minimal API helper extracted from app.js
(function(){
  async function fetchJSON(url, opts){
    try{
      try{ console.debug && console.debug('fetchJSON: url', url, 'opts', opts); }catch(e){}
      opts = opts || {};
      if(typeof opts.credentials === 'undefined') opts.credentials = 'include';
      opts.headers = opts.headers || {};
      try{ if(typeof window !== 'undefined' && window.__AUTH_TOKEN && !opts.headers['Authorization']){ opts.headers['Authorization'] = 'Bearer ' + window.__AUTH_TOKEN; } }catch(e){}
      const r = await fetch(url, opts);
      try{ console.debug && console.debug('fetchJSON: response status', r.status, 'url', url); }catch(e){}
      if(!r.ok){ console.warn('fetch failed', url, r.status); return null; }
      const json = await r.json().catch(()=>null);
      try{ console.debug && console.debug('fetchJSON: parsed json', json); }catch(e){}
      return json;
    }catch(e){ console.warn('fetchJSON failed', e); return null; }
  }

  try{ window.fetchJSON = fetchJSON; window.api = { fetchJSON }; }catch(e){}
})();
