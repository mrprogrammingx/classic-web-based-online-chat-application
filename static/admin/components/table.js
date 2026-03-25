export function createTable(users, options = {}) {
  // options: { onBan, onToggleAdmin, onDelete, isBanned, rowStart }
  const { onBan, onToggleAdmin, onDelete, isBanned, rowStart = 0 } = options;

  const table = document.createElement('table');
  table.className = 'admin-table';

  table.innerHTML = `
    <thead>
      <tr>
        <th>#</th>
        <th>ID</th>
        <th>Username</th>
        <th>Email</th>
        <th>Ban</th>
        <th>Admin</th>
        <th>Delete</th>
      </tr>
    </thead>
  `;

  const tbody = document.createElement('tbody');

  users.forEach((u, idx) => {
    const tr = document.createElement('tr');
    // base cells (add row counter at start)
    const rowNum = rowStart + idx + 1;
    tr.innerHTML = `
      <td>${rowNum}</td>
      <td>${u.id}</td>
      <td>${u.username}</td>
      <td>${u.email}</td>
    `;

    // actions cell placeholders
    const banTd = document.createElement('td');
    const adminTd = document.createElement('td');
    const delTd = document.createElement('td');

    // Ban button
    const banBtn = document.createElement('button');
    banBtn.className = 'btn small';
    const banned = typeof isBanned === 'function' ? isBanned(u) : false;
    banBtn.textContent = banned ? 'Unban' : 'Ban';
    banBtn.addEventListener('click', (e) => { e.preventDefault(); onBan && onBan(u); });
    banTd.appendChild(banBtn);

    // Admin toggle button
    const adminBtn = document.createElement('button');
    adminBtn.className = 'btn small';
    adminBtn.textContent = u.is_admin ? 'Revoke admin' : 'Make admin';
    adminBtn.addEventListener('click', (e) => { e.preventDefault(); onToggleAdmin && onToggleAdmin(u); });
    adminTd.appendChild(adminBtn);

    // Delete button
    const delBtn = document.createElement('button');
    delBtn.className = 'btn small btn-danger';
    delBtn.textContent = 'Delete';
    delBtn.addEventListener('click', (e) => { e.preventDefault(); onDelete && onDelete(u); });
    delTd.appendChild(delBtn);

    tr.appendChild(banTd);
    tr.appendChild(adminTd);
    tr.appendChild(delTd);

    tbody.appendChild(tr);
  });

  table.appendChild(tbody);
  return table;
}