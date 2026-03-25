import { apiPost } from './api.js';
import { confirmModal } from './components/modal.js';

// createUserActions returns an options object suitable for createTable
// params:
//   - getBannedIds: function(user) -> boolean (optional)
//   - refresh: async function to call after action
export function createUserActions({ getBannedIds, refresh } = {}) {
  return {
    isBanned: (u) => {
      try { return typeof getBannedIds === 'function' ? !!getBannedIds(u) : false; } catch (e) { return false; }
    },
    onBan: async (u) => {
      const banned = typeof getBannedIds === 'function' ? !!getBannedIds(u) : false;
      const ok = await confirmModal({ title: banned ? 'Unban user' : 'Ban user', body: `${banned ? 'Unban' : 'Ban'} ${u.username || u.email || u.id}?` });
      if (!ok) return;
      const endpoint = banned ? '/admin/unban_user' : '/admin/ban_user';
      await apiPost(endpoint, { user_id: u.id });
      if (typeof refresh === 'function') await refresh();
    },
    onToggleAdmin: async (u) => {
      const action = u.is_admin ? '/admin/revoke_admin' : '/admin/make_admin';
      const ok = await confirmModal({ title: u.is_admin ? 'Revoke admin' : 'Make admin', body: `${u.is_admin ? 'Revoke admin for' : 'Make admin for'} ${u.username || u.email || u.id}?` });
      if (!ok) return;
      await apiPost(action, { user_id: u.id });
      if (typeof refresh === 'function') await refresh();
    },
    onDelete: async (u) => {
      const ok = await confirmModal({ title: 'Delete user', body: `Delete ${u.username || u.email || u.id}? This cannot be undone.` });
      if (!ok) return;
      await apiPost('/admin/users/delete', { id: u.id });
      if (typeof refresh === 'function') await refresh();
    }
  };
}

// createMessageActions returns an object suitable for message table actions
// params:
//   - refresh: async function to call after action completes
export function createMessageActions({ refresh } = {}) {
  return {
    onDelete: async (m) => {
      const ok = await confirmModal({ title: 'Delete message', body: `Delete message ${m.id}? This will remove the message and any attached files.` });
      if (!ok) return;
      await apiPost('/admin/delete_message', { id: m.id });
      if (typeof refresh === 'function') await refresh();
    }
  };
}

// createRoomActions returns actions for rooms (delete, etc.)
export function createRoomActions({ refresh } = {}) {
  return {
    onDelete: async (r) => {
      const ok = await confirmModal({ title: 'Delete room', body: `Delete room ${r.name || r.id}? This cannot be undone.` });
      if (!ok) return;
      await apiPost('/admin/delete_room', { id: r.id });
      if (typeof refresh === 'function') await refresh();
    }
  };
}
