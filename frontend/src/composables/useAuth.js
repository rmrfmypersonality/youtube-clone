import { reactive } from 'vue'
import { api, setAuthLostHandler } from '../api/client'

const state = reactive({ user: null, ready: false })

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