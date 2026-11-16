<script setup>
import { ref, watch } from 'vue'
import { api } from '../api/client'
import VideoCard from './VideoCard.vue'

const props = defineProps({ excludeId: { type: Number, required: true } })

const videos = ref([])
const loaded = ref(false)
const error = ref('')
let token = 0

async function load() {
  const t = ++token
  loaded.value = false
  error.value = ''
  try {
    const page = await api.videos.list()
    if (t !== token) return
    videos.value = page.items.filter((v) => v.id !== props.excludeId)
  } catch (e) {
    if (t === token) error.value = e.message
  } finally {
    if (t === token) loaded.value = true
  }
}

watch(() => props.excludeId, load, { immediate: true })
</script>

<template>
  <div class="related">
    <p v-if="error" class="error" role="alert">{{ error }}</p>
    <VideoCard v-for="v in videos" :key="v.id" :video="v" compact />
    <p v-if="loaded && !error && !videos.length" class="muted">Других видео пока нет</p>
  </div>
</template>

<style scoped>
.related {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
</style>