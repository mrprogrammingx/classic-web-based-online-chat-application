// Minimal API helper extracted from app.js
(function(){
  async function fetchJSON(url, opts){
    try{
      opts = opts || {};
      if(typeof opts.credentials === 'undefined') opts.credentials = 'include';
      opts.headers = opts.headers || {};
      try{ if(typeof window !== 'undefined' && window.__AUTH_TOKEN && !opts.headers['Authorization']){ opts.headers['Authorization'] = 'Bearer ' + window.__AUTH_TOKEN; } }catch(e){}
      const r = await fetch(url, opts);
      if(!r.ok){ console.warn('fetch failed', url, r.status); return null; }
      const json = await r.json().catch(()=>null);
      return json;
    }catch(e){ console.warn('fetchJSON failed', e); return null; }
  }

  try{ window.fetchJSON = fetchJSON; window.api = { fetchJSON }; }catch(e){}
})();
