import { ref } from 'vue'

const KEY = 'theme'

function read() {
  try {
    return localStorage.getItem(KEY) === 'light' ? 'light' : 'dark'
  } catch {
    return 'dark' // localStorage может быть недоступен (приватный режим)
  }
}

const theme = ref(read())

function apply() {
  document.documentElement.dataset.theme = theme.value
}
apply() // применяем сразу при импорте, до монтирования приложения

function toggleTheme() {
  theme.value = theme.value === 'dark' ? 'light' : 'dark'
  apply()
  try {
    localStorage.setItem(KEY, theme.value)
  } catch {
    /* не критично */
  }
}

export function useTheme() {
  return { theme, toggleTheme }
}