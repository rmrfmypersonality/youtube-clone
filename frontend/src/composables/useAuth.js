import { reactive, watch } from 'vue'
import { api, refreshSession, setAuthLostHandler } from '../api/client'

const state = reactive({ user: null, ready: false })

// Access-кука живёт 15 минут. Пока вкладка открыта, продлеваем сессию заранее:
// <video> не умеет ретраить запросы после 401, а гостевые эндпоинты вместо 401 отвечают 404.
// Используем общий single-flight refreshSession, иначе параллельные refresh сломают ротацию.
const KEEPALIVE_MS = 10 * 60 * 1000
let keepaliveTimer = null
let lastRefresh = Date.now()

async function keepalive() {
  if (await refreshSession()) lastRefresh = Date.now()
}

watch(
  () => state.user?.id,
  (id) => {
    clearInterval(keepaliveTimer)
    keepaliveTimer = null
    if (id) {
      lastRefresh = Date.now()
      keepaliveTimer = setInterval(keepalive, KEEPALIVE_MS)
    }
  },
)

// Вкладка могла проспать (сон ноутбука, фон), и таймер не сработал вовремя
document.addEventListener('visibilitychange', () => {
  if (
    document.visibilityState === 'visible' &&
    state.user &&
    Date.now() - lastRefresh > KEEPALIVE_MS
  ) {
    keepalive()
  }
})

setAuthLostHandler(() => {
  state.user = null
})

let initPromise = null
function init() {
  if (!initPromise) {
    initPromise = api.auth
      .me()
      .then((user) => {
        state.user = user
      })
      .catch(() => {
        state.user = null
      })
      .finally(() => {
        state.ready = true
      })
  }
  return initPromise
}

async function login(email, password) {
  state.user = await api.auth.login({ email, password })
}

async function register(email, username, password) {
  state.user = await api.auth.register({ email, username, password })
}

async function logout() {
  try {
    await api.auth.logout()
  } finally {
    state.user = null
  }
}

export function useAuth() {
  return { state, init, login, register, logout }
}