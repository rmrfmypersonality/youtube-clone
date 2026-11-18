<script setup>
import { VISIBILITY_LABELS } from '../composables/visibility'
defineProps({ playlist: { type: Object, required: true } })
const target = (p) =>
  p.kind === 'liked' ? '/liked' : p.kind === 'watch_later' ? '/watch-later' : `/playlist/${p.id}`
</script>

<template>
  <RouterLink :to="target(playlist)" class="card">
    <div class="cover">
      <img
        v-if="playlist.cover_video_id"
        :src="`/api/videos/${playlist.cover_video_id}/thumbnail`"
        :alt="playlist.title"
        loading="lazy"
      />
      <span class="count">{{ playlist.items_count }} видео</span>
    </div>
    <div class="title">{{ playlist.title }}</div>
    <div v-if="playlist.visibility !== 'public'" class="muted">
      {{ VISIBILITY_LABELS[playlist.visibility] }}
    </div>
  </RouterLink>
</template>

<style scoped>
.card {
  display: block;
  min-width: 0;
  color: var(--text);
}
.cover {
  position: relative;
  aspect-ratio: 16 / 9;
  overflow: hidden;
  border-radius: var(--radius);
  background: var(--surface);
}
.cover img {
  display: block;
  width: 100%;
  height: 100%;
  object-fit: cover;
}
.count {
  position: absolute;
  right: 8px;
  bottom: 8px;
  padding: 1px 6px;
  border-radius: 4px;
  background: rgba(0, 0, 0, 0.8);
  color: #fff;
  font-size: 12px;
  font-weight: 500;
}
.title {
  margin-top: 8px;
  font-weight: 500;
  overflow-wrap: anywhere;
}
</style>