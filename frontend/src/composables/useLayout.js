import { computed, reactive } from 'vue'

const KEY = 'sidebar-expanded'
const desktop = window.matchMedia('(min-width: 1025px)')

function read() {
  try {
    return localStorage.getItem(KEY) !== '0'
  } catch {
    return true
  }
}

const state = reactive({
  expanded: read(), // развёрнут ли постоянный сайдбар
  drawer: false, // открыт ли выезжающий сайдбар
  desktop: desktop.matches,
  watchPage: false, // на странице просмотра сайдбар всегда выезжающий
})

desktop.addEventListener('change', (e) => {
  state.desktop = e.matches
  state.drawer = false
})

// overlay: сайдбар выезжает поверх контента (планшет, телефон, страница просмотра)
const overlay = computed(() => !state.desktop || state.watchPage)

const layoutClass = computed(() => {
  if (overlay.value) return ''
  return state.expanded ? 'offset-full' : 'offset-mini'
})

function toggleSidebar() {
  if (overlay.value) {
    state.drawer = !state.drawer
    return
  }
  state.expanded = !state.expanded
  try {
    localStorage.setItem(KEY, state.expanded ? '1' : '0')
  } catch {
    /* не критично */
  }
}

function closeDrawer() {
  state.drawer = false
}

function setWatchPage(value) {
  state.watchPage = value
  state.drawer = false
}

export function useLayout() {
  return { state, overlay, layoutClass, toggleSidebar, closeDrawer, setWatchPage }
}