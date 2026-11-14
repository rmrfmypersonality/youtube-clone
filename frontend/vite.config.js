import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  server: {
    host: '0.0.0.0',
    port: 5173,
    // На Windows + Docker Desktop inotify через bind-mount не работает, нужен polling
    watch: { usePolling: true },
    proxy: {
      // Через nginx, а не напрямую в api: только nginx умеет X-Accel-Redirect (раздача видео)
      '/api': 'http://nginx',
      '/docs': 'http://api:8000',
      '/openapi.json': 'http://api:8000',
    },
  },
})