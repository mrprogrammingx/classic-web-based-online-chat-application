export function createSearchInput({ placeholder = 'Search...', value = '', onSearch }) {
  const wrapper = document.createElement('div');
  wrapper.className = 'search-control';

  const input = document.createElement('input');
  input.type = 'search';
  input.placeholder = placeholder;
  input.value = value;
  input.className = 'admin-search-input';

  const btn = document.createElement('button');
  btn.className = 'btn small';
  btn.textContent = 'Search';

  btn.onclick = () => {
    if (typeof onSearch === 'function') onSearch(input.value);
  };

  input.addEventListener('keypress', (e) => {
    if (e.key === 'Enter') { e.preventDefault(); btn.click(); }
  });

  wrapper.appendChild(input);
  wrapper.appendChild(btn);
  return wrapper;
}
