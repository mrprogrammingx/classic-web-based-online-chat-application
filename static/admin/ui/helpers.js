export function loading() {
  return `
    <div class="admin-loading">
      <div class="spinner"></div>
      <div>Loading…</div>
    </div>
  `;
}

export function empty(message) {
  return `<div class="admin-empty">${message}</div>`;
}