const BASE = '/api'

export class ApiError extends Error {
  constructor(status, data) {
    super(data?.detail || `HTTP ${status}`)
    this.status = status
    this.data = data
  }
}

async function request(path, options = {}) {
  const res = await fetch(BASE + path, {
    credentials: 'include',
    headers: { 'Content-Type': 'application/json', ...(options.headers || {}) },
    ...options,
  })
  const data = res.status === 204 ? null : await res.json().catch(() => null)
  if (!res.ok) throw new ApiError(res.status, data)
  return data
}

export const api = {
  health: () => request('/health'),
}