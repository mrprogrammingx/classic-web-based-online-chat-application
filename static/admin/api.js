export async function apiGet(path) {
  const res = await fetch(path, { credentials: 'include' });

  if (!res.ok) {
    return { ok: false, status: res.status };
  }

  return { ok: true, data: await res.json() };
}

export async function apiPost(path, body) {
  const res = await fetch(path, {
    method: 'POST',
    credentials: 'include',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body)
  });

  return { ok: res.ok, status: res.status };
}