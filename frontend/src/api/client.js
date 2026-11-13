const BASE = '/api'

// На эти пути 401 означает «неверные данные», а не «протух access», refresh не пробуем
const NO_REFRESH = new Set(['/auth/login', '/auth/register', '/auth/refresh', '/auth/logout'])

export class ApiError extends Error {
  constructor(status, data) {
    super(extractMessage(status, data))
    this.status = status
    this.data = data
  }
}

function extractMessage(status, data) {
  const detail = data?.detail
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail) && detail.length) return detail[0].msg
  return `Ошибка ${status}`
}

let onAuthLost = () => {}
export function setAuthLostHandler(fn) {
  onAuthLost = fn
}

// Одновременные 401 делят один запрос на refresh, иначе ротация сломает сама себя
let refreshing = null
function refreshSession() {
  if (!refreshing) {
    refreshing = fetch(`${BASE}/auth/refresh`, { method: 'POST', credentials: 'include' })
      .then((res) => res.ok)
      .catch(() => false)
      .finally(() => {
        refreshing = null
      })
  }
  return refreshing
}

async function request(method, path, body, retry = true) {
  const headers = {}
  if (body !== undefined) headers['Content-Type'] = 'application/json'

  const res = await fetch(BASE + path, {
    method,
    credentials: 'include',
    headers,
    body: body === undefined ? undefined : JSON.stringify(body),
  })

  if (res.status === 401 && retry && !NO_REFRESH.has(path)) {
    if (await refreshSession()) return request(method, path, body, false)
    onAuthLost()
  }

  const data = res.status === 204 ? null : await res.json().catch(() => null)
  if (!res.ok) throw new ApiError(res.status, data)
  return data
}

export const api = {
  health: () => request('GET', '/health'),
  auth: {
    me: () => request('GET', '/auth/me'),
    login: (payload) => request('POST', '/auth/login', payload),
    register: (payload) => request('POST', '/auth/register', payload),
    logout: () => request('POST', '/auth/logout'),
  },
}