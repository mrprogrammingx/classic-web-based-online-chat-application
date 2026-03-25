import { apiGet } from '../api.js';
import { state } from '../state.js';
import { loading, empty } from './helpers.js';
import { createTable } from '../components/table.js';
import { createPager } from './pager.js';
import { createUserActions } from '../actions.js';
import { createControls } from './controls.js';

export async function renderBanned(container) {
  container.innerHTML = loading();

  const q = new URLSearchParams({
    page: state.users.page,
    per_page: state.users.perPage
  });

  if (state.users.query) q.set('q', state.users.query);

  const res = await apiGet('/admin/banned?' + q);
  if (!res || !res.ok) {
    container.innerHTML = empty('Failed to load banned users');
    return;
  }

  const banned = (res.data && res.data.banned) || [];

  const users = banned.map(b => ({
    id: b.banned_id,
    username: b.username || '',
    email: b.email || '',
    is_admin: !!b.is_admin
  }));

  const actions = createUserActions({ getBannedIds: () => true, refresh: async () => renderBanned(container) });
  const rowStart = (state.users.page - 1) * state.users.perPage;
  container.innerHTML = '';

  container.appendChild(createControls(() => renderBanned(container)));
  container.appendChild(createTable(users, { ...actions, rowStart }));

  // If backend returns total in data.total, use it; otherwise pager will still allow prev/next
  const total = (res.data && res.data.total) || users.length;
  container.appendChild(createPager(total, () => renderBanned(container)));
}