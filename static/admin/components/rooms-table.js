import { escapeHtml } from '../ui/_textutils.js';

export function createRoomsTable(rooms, options = {}) {
  const { onDelete, rowStart = 0 } = options;

  const table = document.createElement('table');
  table.className = 'admin-table rooms-table';

  table.innerHTML = `
    <thead>
      <tr>
        <th>#</th>
        <th>ID</th>
        <th>Name</th>
        <th>Topic</th>
        <th>Actions</th>
      </tr>
    </thead>
  `;

  const tbody = document.createElement('tbody');

  rooms.forEach((r, i) => {
    const tr = document.createElement('tr');
    const rowNum = rowStart + i + 1;
    const numTd = document.createElement('td'); numTd.textContent = rowNum;
    const idTd = document.createElement('td'); idTd.textContent = r.id;
    const nameTd = document.createElement('td'); nameTd.innerHTML = escapeHtml(r.name || '');
    const topicTd = document.createElement('td'); topicTd.innerHTML = escapeHtml(r.topic || '');

    const actionsTd = document.createElement('td');
    const delBtn = document.createElement('button');
    delBtn.className = 'btn small btn-danger';
    delBtn.textContent = 'Delete';
    delBtn.addEventListener('click', (e) => { e.preventDefault(); onDelete && onDelete(r); });
    actionsTd.appendChild(delBtn);

  tr.appendChild(numTd);
  tr.appendChild(idTd);
    tr.appendChild(nameTd);
    tr.appendChild(topicTd);
    tr.appendChild(actionsTd);

    tbody.appendChild(tr);
  });

  table.appendChild(tbody);
  return table;
}
