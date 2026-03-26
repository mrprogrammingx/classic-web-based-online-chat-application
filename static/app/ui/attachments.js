// File attachment handling (moved out of app.js)
(function(){
  function initFileAttachments(){
    const fileInput = document.getElementById('file-input');
    if(!fileInput) return;
    const selectedWrap = document.createElement('div'); selectedWrap.className='selected-file';
    fileInput.parentNode.insertBefore(selectedWrap, fileInput.nextSibling);
    fileInput.addEventListener('change', ()=>{
      selectedWrap.innerHTML = '';
      if(!fileInput.files || fileInput.files.length === 0) return;
      const file = fileInput.files[0];
      const info = document.createElement('div'); info.textContent = `Selected: ${file.name} `;
      const remove = document.createElement('button'); remove.type='button'; remove.textContent='Remove';
      remove.addEventListener('click', ()=>{ fileInput.value=''; selectedWrap.innerHTML=''; });
      info.appendChild(remove);
      selectedWrap.appendChild(info);
    });
  }

  try{ window.initFileAttachments = initFileAttachments; }catch(e){}
})();
