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

function qs(params) {
  const p = new URLSearchParams()
  for (const [key, value] of Object.entries(params)) {
    if (value !== null && value !== undefined && value !== '') p.set(key, value)
  }
  const s = p.toString()
  return s ? `?${s}` : ''
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
    list: (cursor) => request('GET', `/videos${qs({ cursor })}`),
    mine: (cursor) => request('GET', `/videos/mine${qs({ cursor })}`),
    create: (payload) => request('POST', '/videos', payload),
    get: (id) => request('GET', `/videos/${id}`),
    update: (id, payload) => request('PATCH', `/videos/${id}`, payload),
    remove: (id) => request('DELETE', `/videos/${id}`),
    view: (id) => request('POST', `/videos/${id}/view`),
    react: (id, value) => request('PUT', `/videos/${id}/reaction`, { value }),
    shares: {
      list: (id) => request('GET', `/videos/${id}/shares`),
      add: (id, username) => request('POST', `/videos/${id}/shares`, { username }),
      remove: (id, userId) => request('DELETE', `/videos/${id}/shares/${userId}`),
    },
  },
  search: (q, cursor) => request('GET', `/search${qs({ q, cursor })}`),
  comments: {
    list: (videoId, sort, cursor) =>
      request('GET', `/videos/${videoId}/comments${qs({ sort, cursor })}`),
    create: (videoId, payload) => request('POST', `/videos/${videoId}/comments`, payload),
    replies: (id, cursor) => request('GET', `/comments/${id}/replies${qs({ cursor })}`),
    remove: (id) => request('DELETE', `/comments/${id}`),
  },
  channels: {
    get: (handle) => request('GET', `/channels/${handle}`),
    videos: (handle, cursor) => request('GET', `/channels/${handle}/videos${qs({ cursor })}`),
    playlists: (handle) => request('GET', `/channels/${handle}/playlists`),
    update: (payload) => request('PATCH', '/channels/me', payload),
    subscribe: (handle) => request('PUT', `/channels/${handle}/subscription`),
    unsubscribe: (handle) => request('DELETE', `/channels/${handle}/subscription`),
  },
  playlists: {
    mine: (videoId) => request('GET', `/playlists/mine${qs({ video_id: videoId })}`),
    create: (payload) => request('POST', '/playlists', payload),
    get: (id) => request('GET', `/playlists/${id}`),
    update: (id, payload) => request('PATCH', `/playlists/${id}`, payload),
    remove: (id) => request('DELETE', `/playlists/${id}`),
    addItem: (id, videoId) => request('PUT', `/playlists/${id}/items/${videoId}`),
    removeItem: (id, videoId) => request('DELETE', `/playlists/${id}/items/${videoId}`),
  },
    reports: {
    video: (id, payload) => request('POST', `/videos/${id}/report`, payload),
    comment: (id, payload) => request('POST', `/comments/${id}/report`, payload),
  },
  moderation: {
    reports: (status, cursor) => request('GET', `/moderation/reports${qs({ status, cursor })}`),
    dismiss: (id) => request('POST', `/moderation/reports/${id}/dismiss`),
    hideVideo: (id) => request('POST', `/moderation/videos/${id}/hide`),
    unhideVideo: (id) => request('POST', `/moderation/videos/${id}/unhide`),
    hideComment: (id) => request('POST', `/moderation/comments/${id}/hide`),
    unhideComment: (id) => request('POST', `/moderation/comments/${id}/unhide`),
  },
  admin: {
    users: (q, cursor) => request('GET', `/admin/users${qs({ q, cursor })}`),
    updateUser: (id, payload) => request('PATCH', `/admin/users/${id}`, payload),
    audit: (cursor) => request('GET', `/admin/audit${qs({ cursor })}`),
  },
  subscriptions: {
    list: () => request('GET', '/subscriptions'),
    feed: (cursor) => request('GET', `/subscriptions/feed${qs({ cursor })}`),
  },
}