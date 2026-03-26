// Tiny i18n helper (extracted from app.js)
(function(){
  window._STRINGS = window._STRINGS || { en: { ok: 'OK', cancel: 'Cancel', ban: 'Ban', keep: 'Keep', revoke: 'Revoke' } };
  var _locale = 'en';
  function t(key, lang){ lang = lang || _locale; return (window._STRINGS[lang] && window._STRINGS[lang][key]) || window._STRINGS.en[key] || key; }
  function setLocale(lang){ if(!lang) return; _locale = lang; }
  function addStrings(lang, obj){ if(!lang || typeof obj !== 'object') return; window._STRINGS[lang] = Object.assign({}, window._STRINGS[lang] || {}, obj); }
  try{ window.t = t; window.setLocale = setLocale; window.addStrings = addStrings; }catch(e){}
})();
