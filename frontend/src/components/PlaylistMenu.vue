<script setup>
import { ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { api } from '../api/client'
import { useAuth } from '../composables/useAuth'

const props = defineProps({ videoId: { type: Number, required: true } })

const route = useRoute()
const router = useRouter()
const { state: auth } = useAuth()

const open = ref(false)
const lists = ref([])
const loading = ref(false)
const error = ref('')
const newTitle = ref('')
const creating = ref(false)

async function load() {
  loading.value = true
  error.value = ''
  try {
    lists.value = await api.playlists.mine(props.videoId)
  } catch (e) {
    error.value = e.message
  } finally {
    loading.value = false
  }
}

async function toggleOpen() {
  if (!auth.user) {
    router.push({ name: 'login', query: { next: route.fullPath } })
    return
  }
  open.value = !open.value
  if (open.value) await load()
}

async function toggle(pl) {
  error.value = ''
  try {
    if (pl.contains) await api.playlists.removeItem(pl.id, props.videoId)
    else await api.playlists.addItem(pl.id, props.videoId)
    pl.contains = !pl.contains
  } catch (e) {
    error.value = e.message
  }
}

async function create() {
  const title = newTitle.value.trim()
  if (!title || creating.value) return
  creating.value = true
  error.value = ''
  try {
    const pl = await api.playlists.create({ title })
    newTitle.value = ''
    await api.playlists.addItem(pl.id, props.videoId)
  } catch (e) {
    error.value = e.message
  } finally {
    creating.value = false
    await load()
  }
}
</script>

<template>
  <div class="wrap">
    <button type="button" class="chip" @click="toggleOpen">Сохранить</button>
    <div v-if="open" class="backdrop" @click="open = false" />
    <div v-if="open" class="popover">
      <div class="title">Сохранить в…</div>
      <p v-if="loading" class="muted">Загрузка…</p>
      <label v-for="pl in lists" :key="pl.id" class="item">
        <input type="checkbox" :checked="pl.contains" @change="toggle(pl)" />
        <span>{{ pl.title }}</span>
        <span v-if="!pl.is_public" class="muted">🔒</span>
      </label>
      <p v-if="!loading && !lists.length" class="muted">Плейлистов пока нет</p>
      <p v-if="error" class="error" role="alert">{{ error }}</p>
      <form class="new" @submit.prevent="create">
        <input v-model="newTitle" maxlength="100" placeholder="Новый плейлист" />
        <button class="btn" :disabled="creating || !newTitle.trim()">Создать</button>
      </form>
    </div>
  </div>
</template>

<style scoped>
.wrap {
  position: relative;
}
.chip {
  padding: 4px 12px;
  border: none;
  border-radius: 8px;
  background: var(--surface);
  color: var(--text);
  font: inherit;
  cursor: pointer;
}
.chip:hover {
  background: var(--surface-hover);
}
.backdrop {
  position: fixed;
  inset: 0;
  z-index: 10;
}
.popover {
  position: absolute;
  top: 36px;
  left: 0;
  z-index: 11;
  width: 280px;
  padding: 12px 16px;
  border-radius: var(--radius);
  background: var(--surface);
  box-shadow: 0 4px 32px rgba(0, 0, 0, 0.4);
}
.title {
  margin-bottom: 8px;
  font-weight: 500;
}
.item {
  display: flex;
  gap: 8px;
  align-items: center;
  padding: 6px 0;
  cursor: pointer;
  overflow-wrap: anywhere;
}
.new {
  display: flex;
  gap: 8px;
  margin-top: 12px;
}
.new input {
  flex: 1;
  min-width: 0;
  padding: 6px 10px;
  border: 1px solid var(--border);
  border-radius: 8px;
  background: var(--bg);
  color: var(--text);
  font: inherit;
}
</style>