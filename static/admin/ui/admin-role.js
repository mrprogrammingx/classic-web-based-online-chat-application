import { apiGet } from '../api.js';
import { state } from '../state.js';
import { loading, empty } from './helpers.js';
import { createControls } from './controls.js';
import { createTable } from '../components/table.js';
import { createPager } from './pager.js';
import { createUserActions } from '../actions.js';

export async function renderAdminRole(container) {
  container.innerHTML = loading();

  const q = new URLSearchParams({
    page: state.users.page,
    per_page: state.users.perPage,
    filter: 'admins'
  });

  if (state.users.query) q.set('q', state.users.query);

  const res = await apiGet('/admin/users?' + q);
  if (!res || !res.ok) {
    container.innerHTML = empty('Failed to load admins');
    return;
  }

  const data = res.data || { users: [], total: 0 };

  container.innerHTML = '';

  container.appendChild(createControls(() => renderAdminRole(container)));

  const actions = createUserActions({ getBannedIds: (u) => (data.banned_ids || []).includes(u.id), refresh: async () => renderAdminRole(container) });
  const rowStart = (state.users.page - 1) * state.users.perPage;
  container.appendChild(createTable(data.users || [], { ...actions, rowStart }));

  container.appendChild(createPager(data.total || 0, () => renderAdminRole(container)));
}
