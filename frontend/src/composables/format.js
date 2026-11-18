export function formatSize(bytes) {
  if (bytes < 1024 * 1024) return `${Math.max(1, Math.round(bytes / 1024))} КБ`
  if (bytes < 1024 ** 3) return `${(bytes / 1024 / 1024).toFixed(1)} МБ`
  return `${(bytes / 1024 ** 3).toFixed(2)} ГБ`
}

function plural(n, one, few, many) {
  const m10 = n % 10
  const m100 = n % 100
  if (m10 === 1 && m100 !== 11) return one
  if (m10 >= 2 && m10 <= 4 && (m100 < 12 || m100 > 14)) return few
  return many
}

// Целочисленная арифметика, чтобы не ловить 1.1 * 10 = 11.000000000000002
export function formatViews(n) {
  if (n < 1000) return `${n} ${plural(n, 'просмотр', 'просмотра', 'просмотров')}`
  if (n < 1_000_000) {
    const k = n < 10_000 ? Math.floor(n / 100) / 10 : Math.floor(n / 1000)
    return `${String(k).replace('.', ',')} тыс. просмотров`
  }
  const m = n < 10_000_000 ? Math.floor(n / 100_000) / 10 : Math.floor(n / 1_000_000)
  return `${String(m).replace('.', ',')} млн просмотров`
}

const RTF = new Intl.RelativeTimeFormat('ru', { numeric: 'auto' })
const UNITS = [
  ['year', 31_536_000],
  ['month', 2_592_000],
  ['week', 604_800],
  ['day', 86_400],
  ['hour', 3600],
  ['minute', 60],
]

export function formatRelative(iso) {
  const diff = (new Date(iso).getTime() - Date.now()) / 1000
  for (const [unit, seconds] of UNITS) {
    if (Math.abs(diff) >= seconds) return RTF.format(Math.trunc(diff / seconds), unit)
  }
  return 'только что'
}

export function formatDuration(seconds) {
  const s = Math.max(0, Math.round(seconds ?? 0))
  const h = Math.floor(s / 3600)
  const m = Math.floor((s % 3600) / 60)
  const pad = (n) => String(n).padStart(2, '0')
  return h ? `${h}:${pad(m)}:${pad(s % 60)}` : `${m}:${pad(s % 60)}`
}

export function formatSubscribers(n) {
  if (n < 1000) return `${n} ${plural(n, 'подписчик', 'подписчика', 'подписчиков')}`
  if (n < 1_000_000) {
    const k = n < 10_000 ? Math.floor(n / 100) / 10 : Math.floor(n / 1000)
    return `${String(k).replace('.', ',')} тыс. подписчиков`
  }
  const m = n < 10_000_000 ? Math.floor(n / 100_000) / 10 : Math.floor(n / 1_000_000)
  return `${String(m).replace('.', ',')} млн подписчиков`
}

export function formatComments(n) {
  return `${n.toLocaleString('ru-RU')} ${plural(n, 'комментарий', 'комментария', 'комментариев')}`
}