import { apiGet, apiPost } from '../api.js';
import { state } from '../state.js';
import { loading, empty } from './helpers.js';
import { createControls } from './controls.js';
import { createTable } from '../components/table.js';
import { createPager } from './pager.js';
import { createUserActions } from '../actions.js';

export async function renderUsers(container) {
  container.innerHTML = loading();

  const data = await fetchUsers();
  if (!data) {
    container.innerHTML = empty('Failed to load users');
    return;
  }

  container.innerHTML = '';

  container.appendChild(
    createControls(() => renderUsers(container))
  );

  const actions = createUserActions({ getBannedIds: (u) => (data.banned_ids || []).includes(u.id), refresh: async () => renderUsers(container) });
  const rowStart = (state.users.page - 1) * state.users.perPage;
  container.appendChild(createTable(data.users, { ...actions, rowStart }));

  container.appendChild(
    createPager(data.total, () => renderUsers(container))
  );
}

async function fetchUsers() {
  const q = new URLSearchParams({
    page: state.users.page,
    per_page: state.users.perPage,
    q: state.users.query || ''
  });

  const res = await apiGet('/admin/users?' + q);

  if (!res || !res.ok) return null;

  return res.data;
}