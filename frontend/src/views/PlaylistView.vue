<script setup>
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { api } from '../api/client'
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
    const data = isWatchLater.value ? await api.playlists.watchLater() : await api.playlists.get(Number(route.params.id))
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
  } catch (e) {
    actionError.value = e.message
  }
}
</script>

<template>
  <div class="playlist">
    <p v-if="loading" class="muted">Загрузка…</p>
    <p v-else-if="error" class="error" role="alert">{{ error }}</p>

    <template v-else-if="playlist">
      <header class="head">
        <form v-if="editing" @submit.prevent="save">
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

        <template v-else>
          <h1>{{ playlist.title }}</h1>
          <div class="muted">
            <RouterLink :to="`/@${playlist.channel.handle}`">{{ playlist.channel.name }}</RouterLink>
            • {{ playlist.items_count }} видео
            <template v-if="playlist.visibility !== 'public'">
              • {{ VISIBILITY_LABELS[playlist.visibility] }}
            </template>
          </div>
          <p v-if="playlist.description" class="desc">{{ playlist.description }}</p>
          <div v-if="playlist.is_owner && playlist.kind === 'regular'" class="row">
            <button type="button" class="btn" @click="startEdit">Изменить</button>
            <button type="button" class="btn" @click="removePlaylist">Удалить</button>
          </div>
        </template>
        <p v-if="actionError" class="error" role="alert">{{ actionError }}</p>
      </header>

      <p v-if="!playlist.items.length" class="muted">В плейлисте пока нет видео</p>
      <div v-for="video in playlist.items" :key="video.id" class="item">
        <VideoCard :video="video" horizontal class="card" />
        <button v-if="playlist.is_owner" type="button" class="btn" @click="removeItem(video.id)">
          Убрать
        </button>
      </div>
    </template>
  </div>
</template>

<style scoped>
.playlist {
  max-width: 1000px;
  margin: 0 auto;
  padding: 24px 16px;
}
.head {
  margin-bottom: 24px;
}
h1 {
  margin: 0 0 4px;
  font-size: 24px;
  font-weight: 600;
  overflow-wrap: anywhere;
}
.desc {
  margin: 8px 0;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}
.row {
  display: flex;
  gap: 8px;
  margin-top: 12px;
}
.item {
  display: flex;
  gap: 12px;
  align-items: flex-start;
  margin-bottom: 16px;
}
.card {
  flex: 1;
  min-width: 0;
}
</style>