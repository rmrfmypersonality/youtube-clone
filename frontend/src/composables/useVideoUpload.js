import { onBeforeUnmount, reactive } from 'vue'
import { api, uploadVideoFile } from '../api/client'

const POLL_MS = 2000

// phase: idle | uploading | processing | ready | failed | error
export function useVideoUpload() {
  const state = reactive({ phase: 'idle', progress: 0, video: null, error: '' })
  let current = null
  let timer = null

  function stopTimer() {
    clearTimeout(timer)
    timer = null
  }

  async function start(file, meta) {
    stopTimer()
    state.error = ''
    state.progress = 0
    state.phase = 'uploading'
    try {
      // Если запись уже создана (повтор после ошибки), переиспользуем её
      if (!state.video) state.video = await api.videos.create(meta)
      current = uploadVideoFile(state.video.id, file, (p) => {
        state.progress = p
      })
      state.video = await current.promise
      current = null
      state.phase = 'processing'
      poll()
    } catch (e) {
      current = null
      if (state.phase === 'uploading') {
        state.phase = 'error'
        state.error = e.message
      }
    }
  }

  function poll() {
    timer = setTimeout(async () => {
      try {
        state.video = await api.videos.get(state.video.id)
      } catch (e) {
        if (e.status === 404) {
          state.phase = 'failed'
          return
        }
        // временная ошибка сети: продолжаем опрос
      }
      if (state.video.status === 'ready') state.phase = 'ready'
      else if (state.video.status === 'failed') state.phase = 'failed'
      else poll()
    }, POLL_MS)
  }

  function cancel() {
    state.phase = 'idle' // до abort(), чтобы catch в start() не показал ошибку
    current?.abort()
  }

  function reset() {
    stopTimer()
    current?.abort()
    current = null
    state.phase = 'idle'
    state.progress = 0
    state.video = null
    state.error = ''
  }

  onBeforeUnmount(() => {
    stopTimer()
    current?.abort()
  })

  return { state, start, cancel, reset }
}