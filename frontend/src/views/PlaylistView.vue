<script setup>
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { api } from '../api/client'
import PlaylistSidePanel from '../components/PlaylistSidePanel.vue'
import VideoCard from '../components/VideoCard.vue'
import { useAuth } from '../composables/useAuth'
import { VISIBILITY_LABELS } from '../composables/visibility'

const route = useRoute()
const router = useRouter()
const { init } = useAuth()

const isWatchLater = computed(() => route.name === 'watch-later')
const playlist = ref(null)
const loading = ref(true)
const error = ref('')
let token = 0

const editing = ref(false)
const title = ref('')
const description = ref('')
const visibility = ref('public')
const busy = ref(false)
const actionError = ref('')

async function load() {
  const t = ++token
  loading.value = true
  error.value = ''
  playlist.value = null
  editing.value = false
  try {
    await init()
    const data = isWatchLater.value
      ? await api.playlists.watchLater()
      : await api.playlists.get(Number(route.params.id))
    if (t !== token) return
    playlist.value = data
    document.title = `${data.title} — YouTube Clone`
  } catch (e) {
    if (t !== token) return
    error.value = e.status === 404 ? 'Плейлист недоступен или не существует' : e.message
  } finally {
    if (t === token) loading.value = false
  }
}

watch(() => `${String(route.name)}:${route.params.id ?? ''}`, load, { immediate: true })

function startEdit() {
  title.value = playlist.value.title
  description.value = playlist.value.description
  visibility.value = playlist.value.visibility
  actionError.value = ''
  editing.value = true
}

async function save() {
  busy.value = true
  actionError.value = ''
  try {
    const updated = await api.playlists.update(playlist.value.id, {
      title: title.value.trim(),
      description: description.value,
      visibility: visibility.value,
    })
    // updated не содержит items и is_owner, поэтому вливаем в текущий объект
    playlist.value = { ...playlist.value, ...updated }
    editing.value = false
  } catch (e) {
    actionError.value = e.message
  } finally {
    busy.value = false
  }
}

async function removePlaylist() {
  if (!confirm('Удалить плейлист? Видео в нём останутся.')) return
  actionError.value = ''
  try {
    await api.playlists.remove(playlist.value.id)
    router.push(`/@${playlist.value.channel.handle}/playlists`)
  } catch (e) {
    actionError.value = e.message
  }
}

async function removeItem(videoId) {
  actionError.value = ''
  try {
    await api.playlists.removeItem(playlist.value.id, videoId)
    playlist.value.items = playlist.value.items.filter((v) => v.id !== videoId)
    playlist.value.items_count = playlist.value.items.length
    playlist.value.cover_video_id = playlist.value.items[0]?.id ?? null
  } catch (e) {
    actionError.value = e.message
  }
}
// Вручную убирать можно только из своих обычных плейлистов и «Смотреть позже»
const removeLabel = computed(() => {
  if (!playlist.value?.is_owner || playlist.value.kind === 'liked') return ''
  return playlist.value.kind === 'watch_later'
    ? 'Удалить из «Смотреть позже»'
    : 'Удалить из плейлиста'
})
</script>

<template>
  <div class="playlist">
    <p v-if="loading" class="muted">Загрузка…</p>
    <p v-else-if="error" class="error" role="alert">{{ error }}</p>

    <div v-else-if="playlist" class="layout">
      <div class="side">
        <PlaylistSidePanel :playlist="playlist">
          <div v-if="playlist.is_owner && playlist.kind === 'regular' && !editing" class="owner">
            <button type="button" class="pill" @click="startEdit">Изменить</button>
            <button type="button" class="pill" @click="removePlaylist">Удалить</button>
          </div>
        </PlaylistSidePanel>
      </div>

      <div class="list">
        <form v-if="editing" class="edit" @submit.prevent="save">
          <label class="field">
            <span>Название</span>
            <input v-model="title" maxlength="100" required />
          </label>
          <label class="field">
            <span>Описание</span>
            <textarea v-model="description" maxlength="5000" />
          </label>
          <label class="field">
            <span>Доступ</span>
            <select v-model="visibility">
              <option v-for="(label, value) in VISIBILITY_LABELS" :key="value" :value="value">
                {{ label }}
              </option>
            </select>
          </label>
          <div class="row">
            <button type="button" class="btn" @click="editing = false">Отмена</button>
            <button class="btn btn-primary" :disabled="busy || !title.trim()">Сохранить</button>
          </div>
        </form>
        <p v-else-if="playlist.description" class="desc">{{ playlist.description }}</p>
        <p v-if="actionError" class="error" role="alert">{{ actionError }}</p>

        <p v-if="!playlist.items.length" class="muted">Здесь пока ничего нет</p>
        <VideoCard v-for="video in playlist.items" :key="video.id" :video="video" horizontal class="item playlist-card" :remove-label="removeLabel" :hide-watch-later="playlist.kind === 'watch_later'" @remove="(v) => removeItem(v.id)"/>
      </div>
    </div>
  </div>
</template>

<style scoped>
.playlist {
  max-width: 1400px;
  margin: 0 auto;
  padding: 24px;
}
.layout {
  display: flex;
  gap: 24px;
  align-items: flex-start;
}
.side {
  position: sticky;
  top: calc(var(--header-height) + 24px);
  flex: 0 0 360px;
  width: 360px;
}
.list {
  flex: 1;
  min-width: 0;
}
.owner {
  display: flex;
  gap: 8px;
  margin-top: 16px;
}
.edit {
  max-width: 520px;
  margin-bottom: 24px;
}
.row {
  display: flex;
  gap: 8px;
}
.desc {
  margin: 0 0 16px;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}
.item {
  margin-bottom: 16px;
}
@media (max-width: 900px) {
  .playlist {
    padding: 16px 12px;
  }
  .layout {
    flex-direction: column;
    align-items: stretch;
  }
  .side {
    position: static;
    flex: none;
    width: auto;
  }
}
</style>