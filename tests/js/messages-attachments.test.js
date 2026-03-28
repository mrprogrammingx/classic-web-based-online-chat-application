/**
 * tests/js/messages-attachments.test.js
 * Ensure appendMessage renders attached files (images inline, others as links)
 */

describe('message attachments rendering', () => {
  beforeEach(() => {
    document.body.innerHTML = '<div id="messages"></div>';
    jest.resetModules();
  });

  test('appendMessage shows inline image and file link', () => {
    require('../../static/app/data/messages.js');
    const imgFile = { id: 1, url: '/rooms/1/files/1', original_filename: 'pic.png', mime: 'image/png' };
    const otherFile = { id: 2, url: '/rooms/1/files/2', original_filename: 'doc.pdf', mime: 'application/pdf' };
    const msg = { id: 10, user_id: 2, text: 'hi', created_at: Date.now(), files: [imgFile, otherFile] };
    const el = window.appendMessage(msg);
    // el should contain an image and a file-link
    const img = el.querySelector('img');
    const link = el.querySelector('a.file-link');
    expect(img).toBeTruthy();
    expect(img.getAttribute('src')).toBe('/rooms/1/files/1');
    expect(link).toBeTruthy();
    expect(link.getAttribute('href')).toBe('/rooms/1/files/2');
  });
});
