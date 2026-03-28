// File attachment handling (moved out of app.js)
(function(){
  function initFileAttachments(){
    const fileInput = document.getElementById('file-input');
    if(!fileInput) return;
    const selectedWrap = document.createElement('div'); selectedWrap.className='selected-file';
    fileInput.parentNode.insertBefore(selectedWrap, fileInput.nextSibling);
    let currentObjectUrl = null;
    function clearPreview(){
      try{ if(currentObjectUrl){ try{ URL.revokeObjectURL(currentObjectUrl); }catch(e){} currentObjectUrl = null; } }catch(e){}
      try{ selectedWrap.innerHTML = ''; }catch(e){}
    }
    // expose a helper so other modules (composer) can clear and revoke the preview
    try{ window.clearSelectedFilePreview = clearPreview; }catch(e){}

    fileInput.addEventListener('change', ()=>{
      try{
        // cleanup previous preview
        clearPreview();
        if(!fileInput.files || fileInput.files.length === 0) return;
        const file = fileInput.files[0];
        const info = document.createElement('div'); info.textContent = `Selected: ${file.name} `;
        const remove = document.createElement('button'); remove.type='button'; remove.textContent='Remove';
        remove.addEventListener('click', ()=>{ try{ fileInput.value=''; }catch(e){} try{ clearPreview(); }catch(e){} });
        info.appendChild(remove);
        selectedWrap.appendChild(info);

        // if the selected file is an image, show a preview thumbnail
        try{
          if(file.type && file.type.indexOf('image/') === 0){
            // prefer createObjectURL when available; otherwise use FileReader to produce a data URL
            try{
              if(typeof URL !== 'undefined' && typeof URL.createObjectURL === 'function'){
                currentObjectUrl = URL.createObjectURL(file);
                const img = document.createElement('img');
                img.src = currentObjectUrl;
                img.style.maxWidth = '200px';
                img.style.display = 'block';
                img.style.marginTop = '8px';
                img.alt = file.name || 'selected image';
                selectedWrap.appendChild(img);
              } else {
                const reader = new FileReader();
                reader.onload = function(ev){
                  try{
                    const img = document.createElement('img');
                    img.src = ev.target.result;
                    img.style.maxWidth = '200px';
                    img.style.display = 'block';
                    img.style.marginTop = '8px';
                    img.alt = file.name || 'selected image';
                    selectedWrap.appendChild(img);
                  }catch(e){}
                };
                reader.readAsDataURL(file);
              }
            }catch(e){}
          }
        }catch(e){}
      }catch(e){ console.warn('file-input change handler failed', e); }
    });
  }

  try{ window.initFileAttachments = initFileAttachments; }catch(e){}
})();
