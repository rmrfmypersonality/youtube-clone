<script setup>
import { api } from '../api/client'
import InfiniteScroll from '../components/InfiniteScroll.vue'
import VideoCard from '../components/VideoCard.vue'
import { usePagedList } from '../composables/usePagedList'

const { items, loading, done, error, loadMore } = usePagedList((cursor) => api.videos.list(cursor))
</script>

<template>
  <div class="home">
    <div class="grid">
      <VideoCard v-for="video in items" :key="video.id" :video="video" />
    </div>
    <p v-if="done && !items.length" class="muted empty">Пока нет ни одного видео</p>
    <InfiniteScroll :loading="loading" :done="done" :error="error" @load="loadMore" />
  </div>
</template>

<style scoped>
.home {
  padding: 24px;
}
.grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 24px 16px;
}
.empty {
  text-align: center;
}
</style>