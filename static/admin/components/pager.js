export function createPager(page, total, perPage, onChange) {
  const pager = document.createElement('div');
  pager.className = 'admin-pager';

  const totalPages = Math.max(1, Math.ceil(total / perPage));

  const prev = document.createElement('button');
  prev.textContent = 'Prev';
  prev.disabled = page <= 1;

  const next = document.createElement('button');
  next.textContent = 'Next';
  next.disabled = page >= totalPages;

  const info = document.createElement('span');
  info.textContent = `Page ${page} / ${totalPages}`;

  prev.onclick = () => onChange(page - 1);
  next.onclick = () => onChange(page + 1);

  pager.append(prev, next, info);
  return pager;
}