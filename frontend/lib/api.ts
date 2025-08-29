export type ApiResponse<T = any> = T;

export async function apiGet<T>(url: string): Promise<T> {
  const res = await fetch(url);
  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || `GET ${url} failed with ${res.status}`);
  }
  return res.json();
}

export async function apiPost<T>(url: string, body: any): Promise<T> {
  const res = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body ?? {}),
  });
  let data: any = null;
  try { data = await res.json(); } catch {}
  if (!res.ok) {
    const text = data?.detail || data?.message || (await res.text().catch(() => '')) || `POST ${url} failed`;
    throw new Error(text);
  }
  return data as T;
}
