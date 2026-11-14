const BASE = '/api'

// На эти пути 401 означает «неверные данные», а не «протух access», refresh не пробуем
const NO_REFRESH = new Set(['/auth/login', '/auth/register', '/auth/refresh', '/auth/logout'])

const STATUS_MESSAGES = {
  413: 'Файл слишком большой',
  429: 'Слишком много запросов, попробуйте позже',
  502: 'Сервер недоступен',
  503: 'Сервер недоступен',
  504: 'Сервер не ответил вовремя',
}

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
  return STATUS_MESSAGES[status] ?? `Ошибка ${status}`
}

let onAuthLost = () => {}
export function setAuthLostHandler(fn) {
  onAuthLost = fn
}

// Одновременные 401 делят один запрос на refresh, иначе ротация сломает сама себя
let refreshing = null
export function refreshSession() {
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

// Загрузка файла через XHR ради upload.onprogress (у fetch прогресса отправки нет).
// Возвращает { promise, abort }.
export function uploadVideoFile(videoId, file, onProgress) {
  const xhr = new XMLHttpRequest()
  const promise = new Promise((resolve, reject) => {
    xhr.open('PUT', `${BASE}/videos/${videoId}/file`)
    xhr.withCredentials = true
    xhr.setRequestHeader('Content-Type', 'application/octet-stream')
    xhr.upload.onprogress = (e) => {
      if (e.lengthComputable) onProgress(e.loaded / e.total)
    }
    xhr.onload = () => {
      let data = null
      try {
        data = JSON.parse(xhr.responseText)
      } catch {
        /* не JSON (например, HTML-страница ошибки nginx) */
      }
      if (xhr.status >= 200 && xhr.status < 300) resolve(data)
      else reject(new ApiError(xhr.status, data))
    }
    xhr.onerror = () => reject(new ApiError(0, { detail: 'Ошибка сети при загрузке' }))
    xhr.onabort = () => reject(new ApiError(0, { detail: 'Загрузка отменена' }))
    xhr.send(file)
  })
  return { promise, abort: () => xhr.abort() }
}

export const api = {
  health: () => request('GET', '/health'),
  auth: {
    me: () => request('GET', '/auth/me'),
    login: (payload) => request('POST', '/auth/login', payload),
    register: (payload) => request('POST', '/auth/register', payload),
    logout: () => request('POST', '/auth/logout'),
  },
  videos: {
    create: (payload) => request('POST', '/videos', payload),
    get: (id) => request('GET', `/videos/${id}`),
    view: (id) => request('POST', `/videos/${id}/view`),
  },
}