<script setup>
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { api } from '../api/client'
import AppIcon from '../components/AppIcon.vue'
import CommentsSection from '../components/CommentsSection.vue'
import SavePlaylistDialog from '../components/SavePlaylistDialog.vue'
import RelatedVideos from '../components/RelatedVideos.vue'
import ReportDialog from '../components/ReportDialog.vue'
import SubscribeButton from '../components/SubscribeButton.vue'
import { copyText } from '../composables/clipboard'
import { formatRelative, formatSubscribers, formatViews } from '../composables/format'
import { useAuth } from '../composables/useAuth'

const QUALITIES = ['720', '360']
const VISIBILITY_LABELS = { unlisted: 'Доступ по ссылке', private: 'Ограниченный доступ' }

const route = useRoute()
const router = useRouter()
const { state: auth, init, isModerator } = useAuth()

const video = ref(null)
const loading = ref(true)
const error = ref('')
const playerError = ref(false)
const quality = ref('720')
const player = ref(null)
const descOpen = ref(false)
let counted = false
let loadToken = 0

const isOwner = computed(() => !!video.value && auth.user?.id === video.value.owner_id)
const streamUrl = computed(() => `/api/videos/${video.value.id}/stream?quality=${quality.value}`)
const thumbUrl = computed(() => `/api/videos/${video.value.id}/thumbnail`)
const longDescription = computed(
  () => !!video.value && (video.value.description.length > 120 || video.value.description.includes('\n')),
)

async function load(id) {
  const token = ++loadToken
  loading.value = true
  error.value = ''
  playerError.value = false
  descOpen.value = false
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

// --- подписка ---
function onSubscription(res) {
  video.value.is_subscribed = res.subscribed
  video.value.subscribers_count = res.subscribers_count
}

// --- лайки ---
const reacting = ref(false)
const reactError = ref('')

async function react(value) {
  if (!auth.user) {
    router.push({ name: 'login', query: { next: route.fullPath } })
    return
  }
  if (reacting.value) return
  reacting.value = true
  reactError.value = ''
  try {
    const next = video.value.my_reaction === value ? 0 : value // повторный клик снимает реакцию
    const res = await api.videos.react(video.value.id, next)
    video.value.likes_count = res.likes_count
    video.value.my_reaction = res.my_reaction
  } catch (e) {
    reactError.value = e.message
  } finally {
    reacting.value = false
  }
}

// --- поделиться ---
const shareNote = ref('')
let shareTimer = null

async function share() {
  const ok = await copyText(`${location.origin}/watch/${video.value.id}`)
  shareNote.value = ok ? 'Ссылка скопирована' : 'Не удалось скопировать ссылку'
  clearTimeout(shareTimer)
  shareTimer = setTimeout(() => (shareNote.value = ''), 2500)
}

// --- жалоба и модерация ---
const reportOpen = ref(false)

const saveOpen = ref(false)

function openSave() {
  if (!auth.user) {
    router.push({ name: 'login', query: { next: route.fullPath } })
    return
  }
  saveOpen.value = true
}

const moderating = ref(false)
const moderationError = ref('')

async function toggleHidden() {
  if (moderating.value) return
  moderating.value = true
  moderationError.value = ''
  try {
    const res = video.value.hidden_by_moderation
      ? await api.moderation.unhideVideo(video.value.id)
      : await api.moderation.hideVideo(video.value.id)
    video.value.hidden_by_moderation = res.hidden
  } catch (e) {
    moderationError.value = e.message
  } finally {
    moderating.value = false
  }
}
</script>

<template>
  <div class="watch">
    <p v-if="loading" class="muted pad">Загрузка…</p>
    <p v-else-if="error" class="error pad" role="alert">{{ error }}</p>

    <div v-else-if="video" class="layout">
      <div class="primary">
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
            class="pill sm"
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

        <div class="bar">
          <div class="channel">
            <RouterLink :to="`/@${video.channel.handle}`" class="avatar">
              {{ video.channel.name[0]?.toUpperCase() }}
            </RouterLink>
            <div class="channel-info">
              <RouterLink :to="`/@${video.channel.handle}`" class="channel-name">
                {{ video.channel.name }}
              </RouterLink>
              <div class="muted">{{ formatSubscribers(video.subscribers_count) }}</div>
            </div>
            <SubscribeButton
              v-if="!isOwner"
              :handle="video.channel.handle"
              :subscribed="video.is_subscribed"
              @changed="onSubscription"
            />
          </div>

          <div v-if="video.status === 'ready'" class="actions">
            <div class="rate">
              <button
                type="button"
                class="rate-btn like"
                :class="{ active: video.my_reaction === 1 }"
                :aria-pressed="video.my_reaction === 1"
                :disabled="reacting"
                @click="react(1)"
              >
                <AppIcon name="like" :size="20" />
                <span>{{ video.likes_count }}</span>
              </button>
              <button
                type="button"
                class="rate-btn dislike"
                :class="{ active: video.my_reaction === -1 }"
                :aria-pressed="video.my_reaction === -1"
                aria-label="Не нравится"
                :disabled="reacting"
                @click="react(-1)"
              >
                <AppIcon name="dislike" :size="20" />
              </button>
            </div>

            <button type="button" class="pill" @click="share">
              <AppIcon name="share" :size="20" />
              <span>Поделиться</span>
              <button type="button" class="pill" @click="openSave">
                <AppIcon name="playlistAdd" :size="20" />
                <span>Сохранить</span>
              </button>
              v-if="auth.user && !isOwner"
              type="button"
              class="pill"
              @click="reportOpen = true"
            >
              <AppIcon name="flag" :size="20" />
              <span>Пожаловаться</span>
            </button>
            <button
              v-if="isModerator"
              type="button"
              class="pill"
              :disabled="moderating"
              @click="toggleHidden"
            >
              <AppIcon name="shield" :size="20" />
              <span>{{ video.hidden_by_moderation ? 'Вернуть видео' : 'Скрыть видео' }}</span>
            </button>
          </div>
        </div>

        <p v-if="shareNote" class="muted" role="status">{{ shareNote }}</p>
        <p v-if="reactError" class="error" role="alert">{{ reactError }}</p>
        <p v-if="moderationError" class="error" role="alert">{{ moderationError }}</p>
        <ReportDialog
          v-if="reportOpen"
          kind="video"
          :target-id="video.id"
          @close="reportOpen = false"
        />
        <SavePlaylistDialog
          v-if="saveOpen"
          :video-id="video.id"
          @close="saveOpen = false"
        />

        <div class="description" :class="{ open: descOpen }">
          <div class="meta">
            {{ formatViews(video.views_count) }} • {{ formatRelative(video.created_at) }}
          </div>
          <p class="text">{{ video.description || 'Описания нет' }}</p>
          <button v-if="longDescription" type="button" class="link more" @click="descOpen = !descOpen">
            {{ descOpen ? 'Свернуть' : 'Ещё' }}
          </button>
        </div>

        <CommentsSection v-if="video.status === 'ready'" :key="video.id" :video-id="video.id" />
      </div>

      <aside class="secondary">
        <RelatedVideos :exclude-id="video.id" />
      </aside>
    </div>
  </div>
</template>

<style scoped>
.watch {
  max-width: 1754px;
  margin: 0 auto;
  padding: 24px;
}
.pad {
  padding: 0;
}
.layout {
  display: flex;
  gap: 24px;
  align-items: flex-start;
}
.primary {
  flex: 1;
  min-width: 0;
}
.secondary {
  flex: 0 0 402px;
  width: 402px;
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
.title {
  margin: 12px 0 8px;
  font-size: 20px;
  font-weight: 600;
  line-height: 1.3;
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
.bar {
  display: flex;
  flex-wrap: wrap;
  gap: 12px 16px;
  align-items: center;
  justify-content: space-between;
  margin: 8px 0 12px;
}
.channel {
  display: flex;
  align-items: center;
  gap: 12px;
  min-width: 0;
}
.avatar {
  display: grid;
  flex: none;
  place-items: center;
  width: 40px;
  height: 40px;
  border-radius: 50%;
  background: var(--link);
  color: var(--on-link);
  font-weight: 500;
}
.channel-info {
  min-width: 0;
  margin-right: 12px;
}
.channel-name {
  display: block;
  color: var(--text);
  font-weight: 500;
}
.actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
}
.rate {
  display: flex;
  overflow: hidden;
  border-radius: 18px;
  background: var(--surface);
}
.rate-btn {
  display: inline-flex;
  gap: 6px;
  align-items: center;
  height: 36px;
  padding: 0 16px;
  border: none;
  background: none;
  color: var(--text);
  font: inherit;
  font-weight: 500;
  cursor: pointer;
  transition: background 0.15s;
}
.rate-btn:hover {
  background: var(--surface-hover);
}
.rate-btn.like {
  padding-right: 12px;
  border-right: 1px solid var(--border);
}
.rate-btn.dislike {
  padding-left: 12px;
}
.rate-btn.active {
  color: var(--link);
}
.rate-btn:disabled {
  opacity: 0.6;
  cursor: default;
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
  display: -webkit-box;
  margin: 8px 0 0;
  overflow: hidden;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
  -webkit-line-clamp: 3;
  line-clamp: 3;
  -webkit-box-orient: vertical;
}
.description.open .text {
  display: block;
  overflow: visible;
}
.more {
  margin-top: 8px;
}

@media (max-width: 1100px) {
  .layout {
    flex-direction: column;
    align-items: stretch;
  }
  .secondary {
    flex: none;
    width: auto;
  }
}
@media (max-width: 600px) {
  .watch {
    padding: 0 0 24px;
  }
  .primary > :not(.player) {
    margin-left: 12px;
    margin-right: 12px;
  }
  .primary > .description {
    margin-left: 12px;
    margin-right: 12px;
  }
  .player {
    border-radius: 0;
  }
  .secondary {
    padding: 0 12px;
  }
}
</style>