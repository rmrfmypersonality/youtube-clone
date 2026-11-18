<script setup>
import { onBeforeUnmount, onMounted, ref } from 'vue'
import { api } from '../api/client'
import AppIcon from './AppIcon.vue'
import NewPlaylistPanel from './NewPlaylistPanel.vue'

const props = defineProps({ videoId: { type: Number, required: true } })
const emit = defineEmits(['close'])

const lists = ref([])
const loading = ref(true)
const error = ref('')
const creating = ref(false)

async function load() {
  try {
    lists.value = (await api.playlists.mine(props.videoId)).map((p) => ({ ...p, busy: false }))
  } catch (e) {
    error.value = e.message
  } finally {
    loading.value = false
  }
}

async function toggle(pl) {
  if (pl.busy) return
  pl.busy = true
  error.value = ''
  const next = !pl.contains
  try {
    if (next) await api.playlists.addItem(pl.id, props.videoId)
    else await api.playlists.removeItem(pl.id, props.videoId)
    pl.contains = next
  } catch (e) {
    error.value = e.message // галочка остаётся в прежнем состоянии
  } finally {
    pl.busy = false
  }
}

async function onCreated(playlist) {
  creating.value = false
  error.value = ''
  try {
    await api.playlists.addItem(playlist.id, props.videoId)
  } catch (e) {
    error.value = `Плейлист создан, но видео добавить не удалось: ${e.message}`
  }
  await load()
}

function onKey(e) {
  if (e.key !== 'Escape') return
  if (creating.value) creating.value = false
  else emit('close')
}

onMounted(() => {
  load()
  window.addEventListener('keydown', onKey)
})
onBeforeUnmount(() => window.removeEventListener('keydown', onKey))
</script>

<template>
  <Teleport to="body">
    <div class="overlay" @click.self="emit('close')">
      <div class="dialog" role="dialog" aria-modal="true">
        <NewPlaylistPanel v-if="creating" @created="onCreated" @cancel="creating = false" />

        <template v-else>
          <div class="head">
            <h2>Выберите плейлист</h2>
            <button type="button" class="icon-btn" aria-label="Закрыть" @click="emit('close')">
              <AppIcon name="close" />
            </button>
          </div>

          <p v-if="loading" class="muted">Загрузка…</p>
          <label v-for="pl in lists" :key="pl.id" class="item">
            <input
              type="checkbox"
              :checked="pl.contains"
              :disabled="pl.busy"
              @change="toggle(pl)"
            />
            <span class="name">{{ pl.title }}</span>
            <AppIcon v-if="pl.visibility === 'private'" name="lock" :size="20" />
          </label>

          <p v-if="error" class="error" role="alert">{{ error }}</p>
          <button type="button" class="pill new" @click="creating = true">
            <AppIcon name="add" :size="20" />
            <span>Новый</span>
          </button>
        </template>
      </div>
    </div>
  </Teleport>
</template>

<style scoped>
.overlay {
  position: fixed;
  inset: 0;
  z-index: 200;
  display: grid;
  place-items: center;
  padding: 16px;
  background: rgba(0, 0, 0, 0.6);
}
.dialog {
  width: 100%;
  max-width: 360px;
  max-height: 90vh;
  padding: 20px 24px 24px;
  overflow-y: auto;
  border-radius: var(--radius);
  background: var(--surface);
  color: var(--text);
}
.head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
}
h2 {
  margin: 0;
  font-size: 16px;
  font-weight: 500;
}
.item {
  display: flex;
  gap: 16px;
  align-items: center;
  padding: 10px 0;
  cursor: pointer;
}
.item input {
  flex: none;
  width: 18px;
  height: 18px;
  margin: 0;
  accent-color: var(--link);
}
.name {
  flex: 1;
  min-width: 0;
  font-weight: 500;
  overflow-wrap: anywhere;
}
.new {
  width: 100%;
  justify-content: center;
  height: 40px;
  margin-top: 12px;
  background: var(--surface-hover);
}
</style>