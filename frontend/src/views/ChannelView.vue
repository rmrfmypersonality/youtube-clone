<script setup>
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { api } from '../api/client'
import ChannelEditForm from '../components/ChannelEditForm.vue'
import InfiniteScroll from '../components/InfiniteScroll.vue'
import PlaylistCard from '../components/PlaylistCard.vue'
import SubscribeButton from '../components/SubscribeButton.vue'
import VideoCard from '../components/VideoCard.vue'
import { formatSubscribers } from '../composables/format'
import { useAuth } from '../composables/useAuth'
import { usePagedList } from '../composables/usePagedList'

const route = useRoute()
const router = useRouter()
const { init, setChannel } = useAuth()

const handle = computed(() => String(route.params.handle))
const tab = computed(() => (route.params.tab === 'playlists' ? 'playlists' : 'videos'))

const channel = ref(null)
const loading = ref(true)
const error = ref('')
const editing = ref(false)
let token = 0

const {
  items: videos,
  loading: videosLoading,
  done: videosDone,
  error: videosError,
  loadMore: loadVideos,
  reset: resetVideos,
} = usePagedList((cursor) => api.channels.videos(handle.value, cursor))

const playlists = ref([])
const playlistsLoaded = ref(false)
const playlistsError = ref('')
const newTitle = ref('')
const creating = ref(false)
const createError = ref('')

async function load() {
  const t = ++token
  loading.value = true
  error.value = ''
  editing.value = false
  channel.value = null
  resetVideos()
  playlists.value = []
  playlistsLoaded.value = false
  try {
    await init() // сначала выясняем сессию, иначе is_subscribed и is_owner придут как для гостя
    const data = await api.channels.get(handle.value)
    if (t !== token) return
    channel.value = data
    document.title = `${data.name} — YouTube Clone`
  } catch (e) {
    if (t !== token) return
    error.value = e.status === 404 ? 'Канал не найден' : e.message
  } finally {
    if (t === token) loading.value = false
  }
}

watch(handle, load, { immediate: true })

async function loadPlaylists() {
  if (playlistsLoaded.value || !channel.value) return
  const t = token
  playlistsError.value = ''
  try {
    const data = await api.channels.playlists(handle.value)
    if (t !== token) return
    playlists.value = data
    playlistsLoaded.value = true
  } catch (e) {
    if (t === token) playlistsError.value = e.message
  }
}

watch([tab, channel], () => {
  if (tab.value === 'playlists') loadPlaylists()
})

function onSubscription(res) {
  channel.value.is_subscribed = res.subscribed
  channel.value.subscribers_count = res.subscribers_count
}

function onSaved(updated) {
  editing.value = false
  channel.value = updated
  setChannel({ id: updated.id, handle: updated.handle, name: updated.name })
  if (updated.handle !== handle.value) {
    router.replace(`/@${updated.handle}${tab.value === 'playlists' ? '/playlists' : ''}`)
  }
}

async function createPlaylist() {
  const title = newTitle.value.trim()
  if (!title || creating.value) return
  creating.value = true
  createError.value = ''
  try {
    playlists.value.unshift(await api.playlists.create({ title }))
    newTitle.value = ''
  } catch (e) {
    createError.value = e.message
  } finally {
    creating.value = false
  }
}
</script>

<template>
  <div class="channel-page">
    <p v-if="loading" class="muted pad">Загрузка…</p>
    <p v-else-if="error" class="error pad" role="alert">{{ error }}</p>

    <template v-else-if="channel">
      <div class="banner" />

      <header class="head">
        <span class="avatar">{{ channel.name[0]?.toUpperCase() }}</span>
        <div class="meta">
          <h1>{{ channel.name }}</h1>
          <div class="muted">
            @{{ channel.handle }} • {{ formatSubscribers(channel.subscribers_count) }} •
            {{ channel.videos_count }} видео
          </div>
          <p v-if="channel.description && !editing" class="desc">{{ channel.description }}</p>

          <ChannelEditForm
            v-if="editing"
            :channel="channel"
            @saved="onSaved"
            @cancel="editing = false"
          />
          <div v-else class="buttons">
            <button v-if="channel.is_owner" type="button" class="btn" @click="editing = true">
              Настроить канал
            </button>
            <RouterLink v-if="channel.is_owner" to="/studio" class="btn">Мои видео</RouterLink>
            <SubscribeButton
              v-else
              :handle="channel.handle"
              :subscribed="channel.is_subscribed"
              @changed="onSubscription"
            />
          </div>
        </div>
      </header>

      <nav class="tabs">
        <RouterLink
          :to="`/@${channel.handle}`"
          class="tab"
          :class="{ active: tab === 'videos' }"
        >
          Видео
        </RouterLink>
        <RouterLink
          :to="`/@${channel.handle}/playlists`"
          class="tab"
          :class="{ active: tab === 'playlists' }"
        >
          Плейлисты
        </RouterLink>
      </nav>

      <section v-if="tab === 'videos'" class="content">
        <div class="video-grid">
          <VideoCard v-for="video in videos" :key="video.id" :video="video" />
        </div>
        <p v-if="videosDone && !videos.length" class="muted empty">На канале пока нет видео</p>
        <InfiniteScroll
          :loading="videosLoading"
          :done="videosDone"
          :error="videosError"
          @load="loadVideos"
        />
      </section>

      <section v-else class="content">
        <form v-if="channel.is_owner" class="create" @submit.prevent="createPlaylist">
          <input v-model="newTitle" maxlength="100" placeholder="Название нового плейлиста" />
          <button class="btn btn-primary" :disabled="creating || !newTitle.trim()">Создать</button>
        </form>
        <p v-if="createError" class="error" role="alert">{{ createError }}</p>
        <p v-if="playlistsError" class="error" role="alert">{{ playlistsError }}</p>
        <div class="video-grid">
          <PlaylistCard v-for="pl in playlists" :key="pl.id" :playlist="pl" />
        </div>
        <p v-if="playlistsLoaded && !playlists.length" class="muted empty">Плейлистов пока нет</p>
      </section>
    </template>
  </div>
</template>

<style scoped>
.channel-page {
  max-width: 1284px;
  margin: 0 auto;
  padding: 0 24px 24px;
}
.pad {
  padding: 24px 0;
}
.banner {
  height: 160px;
  margin-top: 8px;
  border-radius: var(--radius);
  background: linear-gradient(135deg, #3a3a3a, #1c1c1c 60%, #5b1a1a);
}
.head {
  display: flex;
  gap: 24px;
  padding: 20px 0;
}
.avatar {
  display: grid;
  flex: none;
  place-items: center;
  width: 128px;
  height: 128px;
  border-radius: 50%;
  background: var(--link);
  color: var(--on-link);
  font-size: 48px;
  font-weight: 500;
}
.meta {
  min-width: 0;
}
h1 {
  margin: 0 0 4px;
  font-size: 32px;
  font-weight: 700;
  overflow-wrap: anywhere;
}
.desc {
  margin: 8px 0 0;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}
.buttons {
  display: flex;
  gap: 8px;
  margin-top: 16px;
}
.tabs {
  display: flex;
  gap: 8px;
  border-bottom: 1px solid var(--border);
}
.tab {
  padding: 12px 24px;
  border-bottom: 2px solid transparent;
  color: var(--text-secondary);
  font-weight: 500;
}
.tab.active {
  border-bottom-color: var(--text);
  color: var(--text);
}
.content {
  padding-top: 24px;
}
.create {
  display: flex;
  gap: 8px;
  max-width: 520px;
  margin-bottom: 16px;
}
.create input {
  flex: 1;
  min-width: 0;
  padding: 0 14px;
  height: 36px;
  border: 1px solid var(--border);
  border-radius: 18px;
  background: var(--bg);
  color: var(--text);
  font: inherit;
}
.empty {
  text-align: center;
}
@media (max-width: 600px) {
  .channel-page {
    padding: 0 12px 24px;
  }
  .head {
    flex-direction: column;
    gap: 12px;
  }
  .avatar {
    width: 80px;
    height: 80px;
    font-size: 32px;
  }
  h1 {
    font-size: 24px;
  }
}
</style>