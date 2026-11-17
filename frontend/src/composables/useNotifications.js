import { reactive, watch } from 'vue'
import { api } from '../api/client'
import { useAuth } from './useAuth'

const POLL_MS = 60 * 1000
const state = reactive({ count: 0 })
const { state: auth } = useAuth()
let timer = null

async function refresh() {
  if (!auth.user || document.visibilityState !== 'visible') return
  try {
    state.count = (await api.notifications.count()).count
  } catch {
    /* счётчик не критичен */
  }
}

async function markSeen() {
  await api.notifications.seen()
  state.count = 0
}

// Watcher на уровне модуля, а не компонента: он не должен умирать вместе с компонентом
watch(
  () => auth.user?.id,
  (id) => {
    clearInterval(timer)
    timer = null
    if (id) {
      refresh()
      timer = setInterval(refresh, POLL_MS)
    } else {
      state.count = 0
    }
  },
  { immediate: true },
)

// Вкладка могла проспать: обновляем счётчик сразу при возврате
document.addEventListener('visibilitychange', refresh)

export function useNotifications() {
  return { state, refresh, markSeen }
}