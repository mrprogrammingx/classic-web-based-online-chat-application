import { apiGet } from '../api.js';
import { state } from '../state.js';
import { createMessagesTable } from '../components/messages-table.js';
import { createMessageActions } from '../actions.js';
import { createPager } from './pager.js';
import { createControls } from './controls.js';

export async function renderMessages(container) {
  container.innerHTML = 'Loading...';

  const q = new URLSearchParams({ page: state.users.page, per_page: state.users.perPage });
  if (state.users.query) q.set('q', state.users.query);
  const res = await apiGet('/admin/messages?' + q);
  if (!res.ok) {
    container.innerHTML = 'Failed to load messages';
    return;
  }

  const data = res.data || res;
  const messages = data.messages || [];

  const actions = createMessageActions({ refresh: async () => await renderMessages(container) });
  const rowStart = (state.users.page - 1) * state.users.perPage;
  const table = createMessagesTable(messages, { onDelete: actions.onDelete, rowStart });

  container.innerHTML = '';
  container.appendChild(createControls(() => renderMessages(container)));
  if (messages.length === 0) {
    container.textContent = 'No messages';
  } else {
    container.appendChild(table);
  }

  const total = (data && data.total) || messages.length;
  container.appendChild(createPager(total, () => renderMessages(container)));
}