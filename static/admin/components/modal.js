export function confirmModal({ title, body }) {
  return new Promise(resolve => {
    const overlay = document.createElement('div');
    overlay.className = 'modal-backdrop';

    const box = document.createElement('div');
    box.className = 'modal-box';

    box.innerHTML = `
      <h3>${title}</h3>
      <p>${body}</p>
      <div class="modal-actions">
        <button id="cancel">Cancel</button>
        <button id="ok">OK</button>
      </div>
    `;

    overlay.appendChild(box);
    document.body.appendChild(overlay);

    box.querySelector('#cancel').onclick = () => {
      overlay.remove();
      resolve(false);
    };

    box.querySelector('#ok').onclick = () => {
      overlay.remove();
      resolve(true);
    };
  });
}