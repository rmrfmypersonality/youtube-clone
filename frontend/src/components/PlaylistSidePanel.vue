<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { api } from '../api/client'
import AppIcon from './AppIcon.vue'
import { VISIBILITY_LABELS } from '../composables/visibility'

const props = defineProps({ playlist: { type: Object, required: true } })

const router = useRouter()
const busy = ref(false)
const error = ref('')

async function random() {
  if (busy.value) return
  busy.value = true
  error.value = ''
  try {
    const { video_id } = await api.playlists.random(props.playlist.id)
    if (video_id) router.push(`/watch/${video_id}`)
    else error.value = 'Нет доступных видео'
  } catch (e) {
    error.value = e.message
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <aside class="panel">
    <div class="cover">
      <img
        v-if="playlist.cover_video_id"
        :src="`/api/videos/${playlist.cover_video_id}/thumbnail`"
        :alt="playlist.title"
      />
    </div>
    <h1>{{ playlist.title }}</h1>
    <RouterLink :to="`/@${playlist.channel.handle}`" class="channel">
      {{ playlist.channel.name }}
    </RouterLink>
    <div class="muted">
      {{ playlist.items_count }} видео
      <template v-if="playlist.visibility !== 'public'">
        • {{ VISIBILITY_LABELS[playlist.visibility] }}
      </template>
    </div>

    <div class="buttons">
      <RouterLink
        v-if="playlist.cover_video_id"
        :to="`/watch/${playlist.cover_video_id}`"
        class="pill play"
      >
        <AppIcon name="play" :size="20" />
        <span>Воспроизвести</span>
      </RouterLink>
      <span v-else class="pill play disabled">
        <AppIcon name="play" :size="20" />
        <span>Воспроизвести</span>
      </span>
      <button type="button" class="pill" :disabled="busy || !playlist.items_count" @click="random">
        <AppIcon name="shuffle" :size="20" />
        <span>Случайное</span>
      </button>
    </div>
    <p v-if="error" class="error" role="alert">{{ error }}</p>
    <slot />
  </aside>
</template>

<style scoped>
.panel {
  padding: 24px;
  border-radius: var(--radius);
  background: var(--surface);
}
.cover {
  aspect-ratio: 16 / 9;
  overflow: hidden;
  border-radius: var(--radius);
  background: var(--bg);
}
.cover img {
  display: block;
  width: 100%;
  height: 100%;
  object-fit: cover;
}
h1 {
  margin: 20px 0 8px;
  font-size: 24px;
  font-weight: 700;
  overflow-wrap: anywhere;
}
.channel {
  display: block;
  margin-bottom: 4px;
  color: var(--text);
  font-weight: 500;
}
.buttons {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 20px;
}
.play {
  background: var(--text);
  color: var(--bg);
}
.play:hover {
  background: var(--text);
  filter: brightness(0.9);
}
.play.disabled {
  opacity: 0.5;
  cursor: default;
}
</style>