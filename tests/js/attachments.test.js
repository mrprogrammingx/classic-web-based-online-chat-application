/**
 * tests/js/attachments.test.js
 * Ensure selecting an image shows a preview and that the preview is removed after send.
 */

describe('attachments preview lifecycle', () => {
  beforeEach(() => {
    // minimal chat composer DOM
    document.body.innerHTML = `
      <form id="composer" action="#">
        <input id="message-input" />
        <input id="file-input" type="file" />
        <button type="submit">Send</button>
      </form>
      <div id="messages"></div>
    `;
    // stub globals used by composer and attachments
    window.showToast = window.showToast || function(){};
    window.loadRoomMessages = window.loadRoomMessages || function(){};
    window.loadDialogMessages = window.loadDialogMessages || function(){};
    window.appendMessage = window.appendMessage || function(m){ const d = document.createElement('div'); d.className='msg'; d.textContent = m.text||''; return d; };
    window.messagesEl = document.getElementById('messages');
    // ensure modules can be required fresh
    jest.resetModules();
  });

  afterEach(() => {
    // cleanup
    document.body.innerHTML = '';
    jest.resetAllMocks && jest.resetAllMocks();
  });

  test('image preview appears on file select and is cleared after successful send', async () => {
    // require attachments module which binds change handler
    require('../../static/app/ui/attachments.js');
    // initialize attachments (it exposes window.initFileAttachments)
    if(typeof window.initFileAttachments === 'function') window.initFileAttachments();

    // Simulate selecting an image file by constructing a Blob and setting file input.files
  const blob = new Blob(['fake image content'], { type: 'image/png' });
  const file = new File([blob], 'test.png', { type: 'image/png' });
  const fileInput = document.getElementById('file-input');
  // create a minimal FileList-like object compatible with jsdom
  const fileList = { 0: file, length: 1, item: function(i){ return this[0]; } };
  Object.defineProperty(fileInput, 'files', { value: fileList, writable: true });
    fileInput.dispatchEvent(new Event('change'));

    // Preview element should exist and contain an img. FileReader may be async in jsdom; poll briefly.
    const selWrap = document.querySelector('.selected-file');
    expect(selWrap).toBeTruthy();
    let img = null;
    for(let i=0;i<20;i++){
      img = selWrap.querySelector('img');
      if(img) break;
      await new Promise(r=>setTimeout(r,10));
    }
    expect(img).toBeTruthy();
    expect(img.getAttribute('src')).toBeTruthy();

    // stub XHR send used by composer for file upload
    // We'll intercept XMLHttpRequest to simulate successful upload response
    const originalXHR = global.XMLHttpRequest;
    function FakeXHR(){
      this.requestHeaders = {};
      this.upload = {};
      this._listeners = {};
      this.open = function(){};
      this.setRequestHeader = function(k,v){ this.requestHeaders[k]=v; };
      this.addEventListener = function(evt, cb){ this._listeners[evt] = cb; };
      this.upload.addEventListener = function(evt, cb){ this.upload[evt] = cb; };
      this.send = (fd) => {
        // simulate progress then load
        if(typeof this.upload.onprogress === 'function'){
          this.upload.onprogress({ lengthComputable: true, loaded: 50, total: 100 });
          this.upload.onprogress({ lengthComputable: true, loaded: 100, total: 100 });
        }
        // simulate server response containing message and file metadata
        this.responseText = JSON.stringify({ message: { id: 1, room_id: 1, user_id: 1, text: 'hi', created_at: Date.now() }, file: { id: 7, url: '/rooms/1/files/7', original_filename: 'test.png', mime: 'image/png' } });
        if(typeof this.onload === 'function') this.onload();
        if(this._listeners['load']) this._listeners['load']();
      };
    }
    global.XMLHttpRequest = FakeXHR;

    // require composer module and submit
    require('../../static/app/lib/composer.js');
    // ensure a current room is present so composer proceeds with upload
    window.currentRoom = { id: 1 };
    window.isDialog = false;
    // Call the composer submit handler directly (app.js normally wires the form submit to this)
    if(typeof window.handleComposerSubmit === 'function'){
      await window.handleComposerSubmit(new Event('submit'));
    } else {
      // fallback: dispatch event
      const comp = document.getElementById('composer');
      comp.dispatchEvent(new Event('submit'));
    }

    // allow async handlers to run and poll for preview cleared
    let cleared = false;
    for(let i=0;i<20;i++){
      const selAfter = document.querySelector('.selected-file');
      if(selAfter && selAfter.innerHTML.trim() === ''){ cleared = true; break; }
      await new Promise(r=>setTimeout(r,10));
    }
    expect(cleared).toBe(true);

    // restore XHR
    global.XMLHttpRequest = originalXHR;
  });
});
