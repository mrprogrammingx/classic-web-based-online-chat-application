import { apiGet, apiPost } from '../api.js';
import { state } from '../state.js';
import { loading, empty } from './helpers.js';
import { createControls } from './controls.js';
import { createTable } from '../components/table.js';
import { createPager } from './pager.js';
import { createUserActions } from '../actions.js';

export async function renderUsers(container) {
  container.innerHTML = loading();

  let data = null;
  try{
    data = await fetchUsers();
    console.debug('renderUsers: fetched users', data && data.users && data.users.length);
  }catch(err){
    console.error('renderUsers: fetchUsers failed', err);
  }

  if (!data) {
    container.innerHTML = empty('Failed to load users');
    return;
  }

  container.innerHTML = '';
  container.appendChild(
    createControls(() => renderUsers(container))
  );

  // Backwards-compat wrapper: tests and legacy code expect a `.admin-list` element.
  const listWrap = document.createElement('div');
  listWrap.className = 'admin-list';

  const actions = createUserActions({ getBannedIds: (u) => (data.banned_ids || []).includes(u.id), refresh: async () => renderUsers(container) });
  const rowStart = (state.users.page - 1) * state.users.perPage;
  const table = createTable(data.users, { ...actions, rowStart });
  listWrap.appendChild(table);

  listWrap.appendChild(
    createPager(data.total, () => renderUsers(container))
  );

  container.appendChild(listWrap);
}

async function fetchUsers() {
  const q = new URLSearchParams({
    page: state.users.page,
    per_page: state.users.perPage,
    q: state.users.query || ''
  });

  try{
    const res = await apiGet('/admin/users?' + q);
    if (!res || !res.ok) {
      console.warn('fetchUsers: apiGet failed', res && res.status);
      return null;
    }
    console.debug('fetchUsers: apiGet ok, data keys=', Object.keys(res.data || {}));
    return res.data;
  }catch(e){
    console.error('fetchUsers: exception', e);
    return null;
  }
}