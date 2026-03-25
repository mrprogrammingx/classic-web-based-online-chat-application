import { state } from '../state.js';

export function createPager(total, onChange) {
  const wrapper = document.createElement('div');
  wrapper.className = 'pager';

  const prev = document.createElement('button');
  prev.className = 'btn small pager-btn';
  prev.textContent = 'Prev';
  prev.disabled = state.users.page <= 1;

  const next = document.createElement('button');
  next.className = 'btn small pager-btn';
  next.textContent = 'Next';

  prev.onclick = () => {
    state.users.page--;
    onChange();
  };

  next.onclick = () => {
    state.users.page++;
    onChange();
  };

  wrapper.appendChild(prev);
  wrapper.appendChild(next);

  return wrapper;
}