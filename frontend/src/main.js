import { createApp } from 'vue'
import '@fontsource/roboto/latin-400.css'
import '@fontsource/roboto/latin-500.css'
import '@fontsource/roboto/latin-700.css'
import '@fontsource/roboto/cyrillic-400.css'
import '@fontsource/roboto/cyrillic-500.css'
import '@fontsource/roboto/cyrillic-700.css'
import App from './App.vue'
import router from './router'
import './composables/useTheme' // применяет сохранённую тему до монтирования
import './styles/theme.css'
import './styles/base.css'

createApp(App).use(router).mount('#app')