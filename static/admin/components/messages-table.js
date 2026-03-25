import { escapeHtml } from '../ui/_textutils.js';

// Map message objects into a user-like shape for createTable, but with
// message-specific columns: ID, Room, Author, Text, Created, Delete
export function createMessagesTable(messages, options = {}) {
  const { onDelete, rowStart = 0 } = options;

  const table = document.createElement('table');
  table.className = 'admin-table messages-table';

  table.innerHTML = `
    <thead>
      <tr>
        <th>#</th>
        <th>ID</th>
        <th>Room</th>
        <th>Author</th>
        <th>Text</th>
        <th>Created</th>
        <th>Delete</th>
      </tr>
    </thead>
  `;

  const tbody = document.createElement('tbody');

  messages.forEach((m, i) => {
    const tr = document.createElement('tr');
    const rowNum = rowStart + i + 1;
    const numTd = document.createElement('td'); numTd.textContent = rowNum;
    const idTd = document.createElement('td'); idTd.textContent = m.id;
    const roomTd = document.createElement('td'); roomTd.textContent = m.room_name || m.room_id || '';
    const authorTd = document.createElement('td'); authorTd.textContent = m.username || m.user_id || 'unknown';
    const textTd = document.createElement('td'); textTd.innerHTML = escapeHtml((m.text || '').slice(0, 200));
    const createdTd = document.createElement('td'); createdTd.textContent = m.created_at || '';

    const delTd = document.createElement('td');
    const delBtn = document.createElement('button');
    delBtn.className = 'btn small btn-danger';
    delBtn.textContent = 'Delete';
    delBtn.addEventListener('click', (e) => { e.preventDefault(); onDelete && onDelete(m); });
    delTd.appendChild(delBtn);

  tr.appendChild(numTd);
  tr.appendChild(idTd);
    tr.appendChild(roomTd);
    tr.appendChild(authorTd);
    tr.appendChild(textTd);
    tr.appendChild(createdTd);
    tr.appendChild(delTd);

    tbody.appendChild(tr);
  });

  table.appendChild(tbody);
  return table;
}
