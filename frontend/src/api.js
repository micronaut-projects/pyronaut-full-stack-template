// Thin fetch helper shared by every screen.
//
// Once `pyronaut process` is running, `npm run generate-client` replaces the
// hand-written calls below with the typed SDK generated from the compile-time
// OpenAPI document (see openapi-ts.config.ts).
// Authentication rides an HttpOnly cookie, so nothing here touches a token.

export async function request(url, options = {}) {
  const response = await fetch(url, {
    credentials: 'same-origin',
    headers: options.body ? { 'Content-Type': 'application/json' } : undefined,
    ...options,
  });
  const body = response.status === 204 ? null : await response.json().catch(() => null);
  if (!response.ok) {
    const error = new Error(body?.message || `Request failed (${response.status})`);
    error.status = response.status;
    error.errors = body?.errors || {};
    throw error;
  }
  return body;
}

export const api = {
  login: (email, password) =>
    request('/api/v1/login', {
      method: 'POST',
      body: JSON.stringify({ username: email, password }),
    }),
  signup: (payload) =>
    request('/api/v1/users/signup', { method: 'POST', body: JSON.stringify(payload) }),
  me: () => request('/api/v1/users/me'),
  updateMe: (payload) =>
    request('/api/v1/users/me', { method: 'PATCH', body: JSON.stringify(payload) }),
  updatePassword: (payload) =>
    request('/api/v1/users/me/password', { method: 'PATCH', body: JSON.stringify(payload) }),
  recoverPassword: (email) =>
    request(`/api/v1/password-recovery/${encodeURIComponent(email)}`, { method: 'POST' }),
  resetPassword: (payload) =>
    request('/api/v1/reset-password', { method: 'POST', body: JSON.stringify(payload) }),
  items: (page = 0) => request(`/api/v1/items?page=${page}`),
  createItem: (payload) =>
    request('/api/v1/items', { method: 'POST', body: JSON.stringify(payload) }),
  updateItem: (id, payload) =>
    request(`/api/v1/items/${id}`, { method: 'PUT', body: JSON.stringify(payload) }),
  deleteItem: (id) => request(`/api/v1/items/${id}`, { method: 'DELETE' }),
  users: (page = 0) => request(`/api/v1/users?page=${page}`),
};
