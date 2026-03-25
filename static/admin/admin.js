import { renderUsers } from './ui/users.js';
import { renderAdminRole } from './ui/admin-role.js';
import { renderBanned } from './ui/banned.js';
import { renderRooms } from './ui/rooms.js';
import { renderMessages } from './ui/messages.js';

function initAdminUI() {
  const root = document.getElementById('admin-content');
  if (!root) return;

  const tabs = createTabs();
  const container = document.createElement('div');

  root.innerHTML = '';
  root.appendChild(tabs);
  root.appendChild(container);

  function setActive(btn) {
    tabs.querySelectorAll('button').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
  }

  function bind(btn, renderer) {
    btn.addEventListener('click', () => {
      setActive(btn);
      renderer(container);
    });
  }

  const [usersBtn, adminsBtn, bannedBtn, roomsBtn, messagesBtn] = tabs.children;

  bind(usersBtn, renderUsers);
  bind(adminsBtn, renderAdminRole);
  bind(bannedBtn, renderBanned);
  bind(roomsBtn, renderRooms);
  bind(messagesBtn, renderMessages);

  usersBtn.click(); // default
}

function createTabs() {
  const tabs = document.createElement('div');
  tabs.className = 'admin-tabs';

  ['Users', 'Admins', 'Banned', 'Rooms', 'Messages'].forEach(name => {
    const btn = document.createElement('button');
    btn.className = 'btn small';
    btn.textContent = name;
    tabs.appendChild(btn);
  });

  return tabs;
}

document.addEventListener('DOMContentLoaded', initAdminUI);