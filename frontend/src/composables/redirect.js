export function safeNext(value) {
  const next = String(value || '')
  return next.startsWith('/') && !next.startsWith('//') ? next : '/'
}