import { apiGet } from '../api.js';
import { state } from '../state.js';
import { createRoomsTable } from '../components/rooms-table.js';
import { createRoomActions } from '../actions.js';
import { createControls } from './controls.js';

export async function renderRooms(container) {
  container.innerHTML = 'Loading...';

  const q = new URLSearchParams({ page: state.users.page, per_page: state.users.perPage });
  if (state.users.query) q.set('q', state.users.query);
  const res = await apiGet('/admin/rooms?' + q);
  if (!res || !res.ok) {
    container.innerHTML = 'Failed';
    return;
  }

  const rooms = (res.data && res.data.rooms) || [];

  const actions = createRoomActions({ refresh: async () => await renderRooms(container) });
  const rowStart = (state.users.page - 1) * state.users.perPage;
  const table = createRoomsTable(rooms, { onDelete: actions.onDelete, rowStart });

  container.innerHTML = '';
  container.appendChild(createControls(() => renderRooms(container)));
  container.appendChild(table);
  const total = (res.data && res.data.total) || rooms.length;
  import('./pager.js').then(mod => container.appendChild(mod.createPager(total, () => renderRooms(container))));
}