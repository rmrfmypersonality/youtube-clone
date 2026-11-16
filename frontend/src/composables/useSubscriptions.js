import { reactive, watch } from 'vue'
import { api } from '../api/client'
import { useAuth } from './useAuth'

const state = reactive({ channels: [] })
const { state: auth } = useAuth()

async function reload() {
  try {
    state.channels = await api.subscriptions.list()
  } catch {
    /* список в сайдбаре не критичен */
  }
}

// Watcher на уровне модуля, а не компонента: он не должен умирать вместе с компонентом
watch(
  () => auth.user?.id,
  (id) => {
    if (id) reload()
    else state.channels = []
  },
  { immediate: true },
)

export function useSubscriptions() {
  return { state, reload }
}