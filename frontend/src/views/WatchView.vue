<script setup>
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { api } from '../api/client'
import { useAuth } from '../composables/useAuth'
import { formatRelative, formatViews } from '../composables/format'

const QUALITIES = ['720', '360']
const VISIBILITY_LABELS = { unlisted: 'Доступ по ссылке', private: 'Ограниченный доступ' }

const route = useRoute()
const { state: auth, init } = useAuth()

const video = ref(null)
const loading = ref(true)
const error = ref('')
const playerError = ref(false)
const quality = ref('720')
const player = ref(null)
let counted = false
let loadToken = 0

const isOwner = computed(() => !!video.value && auth.user?.id === video.value.owner_id)
const streamUrl = computed(() => `/api/videos/${video.value.id}/stream?quality=${quality.value}`)
const thumbUrl = computed(() => `/api/videos/${video.value.id}/thumbnail`)

async function load(id) {
  const token = ++loadToken
  loading.value = true
  error.value = ''
  playerError.value = false
  video.value = null
  quality.value = '720'
  counted = false
  try {
    await init() // сначала выясняем сессию, иначе приватное видео вернёт 404 как гостю
    const data = await api.videos.get(id)
    if (token !== loadToken) return
    video.value = data
    document.title = `${data.title} — YouTube Clone`
  } catch (e) {
    if (token !== loadToken) return
    error.value = e.status === 404 ? 'Видео недоступно или не существует' : e.message
  } finally {
    if (token === loadToken) loading.value = false
  }
}

watch(() => route.params.id, (id) => id && load(id), { immediate: true })

onBeforeUnmount(() => {
  loadToken++
  document.title = 'YouTube Clone'
})

async function onPlay() {
  if (counted || !video.value) return
  counted = true
  try {
    video.value.views_count = (await api.videos.view(video.value.id)).views_count
  } catch {
    /* счётчик не критичен для просмотра */
  }
}

// Смена качества с сохранением позиции и состояния паузы
function setQuality(q) {
  if (q === quality.value) return
  const el = player.value
  const time = el?.currentTime ?? 0
  const wasPlaying = !!el && !el.paused
  playerError.value = false
  quality.value = q
  el?.addEventListener(
    'loadedmetadata',
    () => {
      el.currentTime = time
      if (wasPlaying) el.play().catch(() => {})
    },
    { once: true },
  )
}
</script>

<template>
  <div class="watch">
    <p v-if="loading" class="muted">Загрузка…</p>
    <p v-else-if="error" class="error" role="alert">{{ error }}</p>

    <template v-else-if="video">
      <div v-if="video.status === 'ready'" class="player">
        <video
          ref="player"
          :src="streamUrl"
          :poster="thumbUrl"
          controls
          playsinline
          preload="metadata"
          @play="onPlay"
          @error="playerError = true"
        />
      </div>
      <div v-else class="player placeholder">
        <span v-if="video.status === 'failed'">Не удалось обработать видео</span>
        <span v-else>Видео ещё обрабатывается…</span>
      </div>

      <p v-if="playerError" class="error" role="alert">
        Не удалось загрузить видео. Обновите страницу.
      </p>

      <div v-if="video.status === 'ready'" class="quality">
        <button
          v-for="q in QUALITIES"
          :key="q"
          type="button"
          class="chip"
          :class="{ active: quality === q }"
          @click="setQuality(q)"
        >
          {{ q }}p
        </button>
      </div>

      <h1 class="title">{{ video.title }}</h1>

      <p v-if="video.hidden_by_moderation" class="banner">
        Видео скрыто модератором{{ isOwner ? '. Его видите только вы и модераторы.' : '.' }}
      </p>
      <p v-if="isOwner && VISIBILITY_LABELS[video.visibility]" class="badge">
        {{ VISIBILITY_LABELS[video.visibility] }}
      </p>

      <div class="channel">
        <span class="avatar">{{ video.channel.name[0]?.toUpperCase() }}</span>
        <div>
          <div class="channel-name">{{ video.channel.name }}</div>
          <div class="muted">@{{ video.channel.handle }}</div>
        </div>
      </div>

      <div class="description">
        <div class="meta">
          {{ formatViews(video.views_count) }} • {{ formatRelative(video.created_at) }}
        </div>
        <p class="text">{{ video.description || 'Описания нет' }}</p>
      </div>
    </template>
  </div>
</template>

<style scoped>
.watch {
  max-width: 1000px;
  margin: 0 auto;
  padding: 24px 16px;
}
.muted {
  color: var(--text-secondary);
}
.player {
  aspect-ratio: 16 / 9;
  overflow: hidden;
  background: #000;
  border-radius: var(--radius);
}
.player video {
  display: block;
  width: 100%;
  height: 100%;
}
.placeholder {
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--surface);
  color: var(--text-secondary);
}
.quality {
  display: flex;
  gap: 8px;
  margin-top: 10px;
}
.chip {
  padding: 4px 12px;
  border: none;
  border-radius: 8px;
  background: var(--surface);
  color: var(--text);
  font: inherit;
  cursor: pointer;
  transition: background 0.15s;
}
.chip:hover {
  background: var(--surface-hover);
}
.chip.active {
  background: var(--text);
  color: var(--bg);
}
.title {
  margin: 16px 0 8px;
  font-size: 20px;
  font-weight: 600;
  overflow-wrap: anywhere;
}
.banner {
  margin: 0 0 8px;
  padding: 10px 12px;
  border-radius: 8px;
  background: var(--surface);
  color: var(--danger);
}
.badge {
  display: inline-block;
  margin: 0 0 8px;
  padding: 2px 10px;
  border-radius: 8px;
  background: var(--surface);
  color: var(--text-secondary);
}
.channel {
  display: flex;
  align-items: center;
  gap: 12px;
  margin: 8px 0 16px;
}
.avatar {
  display: grid;
  place-items: center;
  width: 40px;
  height: 40px;
  border-radius: 50%;
  background: var(--link);
  color: #0f0f0f;
  font-weight: 500;
}
.channel-name {
  font-weight: 500;
}
.description {
  padding: 12px;
  border-radius: var(--radius);
  background: var(--surface);
}
.meta {
  font-weight: 500;
}
.text {
  margin: 8px 0 0;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}
</style>