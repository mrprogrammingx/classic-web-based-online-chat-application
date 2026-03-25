export function createSearch(onSearch) {
  const wrap = document.createElement('div');
  wrap.className = 'admin-search';

  const input = document.createElement('input');
  input.placeholder = 'Search...';

  const btn = document.createElement('button');
  btn.textContent = 'Search';

  btn.onclick = () => onSearch(input.value);

  wrap.append(input, btn);
  return wrap;
}