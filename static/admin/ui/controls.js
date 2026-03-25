import { state } from '../state.js';
import { createSearchInput } from '../components/search.js';

export function createControls(onChange) {
  const wrapper = document.createElement('div');
  wrapper.className = 'admin-controls';

  const search = createSearchInput({ placeholder: 'Search users...', value: state.users.query || '', onSearch: (v) => {
    state.users.query = v;
    state.users.page = 1;
    onChange();
  }});

  wrapper.appendChild(search);
  return wrapper;
}