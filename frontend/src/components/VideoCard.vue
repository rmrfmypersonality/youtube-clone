<script setup>
import { formatDuration, formatRelative, formatViews } from '../composables/format'

defineProps({
  video: { type: Object, required: true },
  horizontal: Boolean, // результаты поиска: превью слева, текст справа
  compact: Boolean, // правая колонка на странице просмотра
})
</script>

<template>
  <article class="card" :class="{ horizontal, compact }">
    <RouterLink :to="`/watch/${video.id}`" class="thumb">
      <img :src="`/api/videos/${video.id}/thumbnail`" :alt="video.title" loading="lazy" />
      <span class="duration">{{ formatDuration(video.duration_seconds) }}</span>
    </RouterLink>
    <div class="info">
      <RouterLink
        :to="`/@${video.channel.handle}`"
        class="avatar"
        :aria-label="video.channel.name"
      >
        {{ video.channel.name[0]?.toUpperCase() }}
      </RouterLink>
      <div class="text">
        <RouterLink :to="`/watch/${video.id}`" class="title">{{ video.title }}</RouterLink>
        <RouterLink :to="`/@${video.channel.handle}`" class="channel">
          {{ video.channel.name }}
        </RouterLink>
        <div class="muted">
          {{ formatViews(video.views_count) }} • {{ formatRelative(video.created_at) }}
        </div>
      </div>
    </div>
  </article>
</template>

<style scoped>
.card {
  display: flex;
  flex-direction: column;
  gap: 12px;
  min-width: 0;
}
.thumb {
  position: relative;
  display: block;
  aspect-ratio: 16 / 9;
  overflow: hidden;
  border-radius: var(--radius);
  background: var(--surface);
}
.thumb img {
  display: block;
  width: 100%;
  height: 100%;
  object-fit: cover;
}
.duration {
  position: absolute;
  right: 8px;
  bottom: 8px;
  padding: 1px 4px;
  border-radius: 4px;
  background: rgba(0, 0, 0, 0.8);
  color: #fff;
  font-size: 12px;
  font-weight: 500;
}
.info {
  display: flex;
  gap: 12px;
  min-width: 0;
}
.avatar {
  display: grid;
  flex: none;
  place-items: center;
  width: 36px;
  height: 36px;
  border-radius: 50%;
  background: var(--link);
  color: var(--on-link);
  font-weight: 500;
}
.text {
  min-width: 0;
}
.title {
  display: -webkit-box;
  margin-bottom: 4px;
  overflow: hidden;
  color: var(--text);
  font-size: 16px;
  font-weight: 500;
  line-height: 1.3;
  overflow-wrap: anywhere;
  -webkit-line-clamp: 2;
  line-clamp: 2;
  -webkit-box-orient: vertical;
}
.channel {
  display: block;
  color: var(--text-secondary);
}
.channel:hover {
  color: var(--text);
}

.horizontal,
.compact {
  flex-direction: row;
}
.horizontal .avatar,
.compact .avatar {
  display: none;
}
.horizontal .thumb {
  flex: 0 0 360px;
  max-width: 45%;
}
.compact {
  gap: 8px;
}
.compact .thumb {
  flex: 0 0 168px;
}
.compact .title {
  font-size: 14px;
}
.compact .info {
  font-size: 12px;
}
@media (max-width: 600px) {
  .horizontal {
    flex-direction: column;
  }
  .horizontal .thumb {
    flex: none;
    max-width: none;
  }
}
</style>