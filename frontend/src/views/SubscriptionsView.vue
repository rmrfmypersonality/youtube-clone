<script setup>
import { api } from '../api/client'
import InfiniteScroll from '../components/InfiniteScroll.vue'
import VideoCard from '../components/VideoCard.vue'
import { usePagedList } from '../composables/usePagedList'

const { items, loading, done, error, loadMore } = usePagedList((cursor) =>
  api.subscriptions.feed(cursor),
)
</script>

<template>
  <div class="subs">
    <h1>Подписки</h1>
    <div class="video-grid">
      <VideoCard v-for="video in items" :key="video.id" :video="video" />
    </div>
    <p v-if="done && !items.length" class="muted empty">
      Здесь появятся новые видео каналов, на которые вы подписаны.
    </p>
    <InfiniteScroll :loading="loading" :done="done" :error="error" @load="loadMore" />
  </div>
</template>

<style scoped>
.subs {
  padding: 24px;
}
h1 {
  margin: 0 0 16px;
  font-size: 22px;
  font-weight: 500;
}
.empty {
  text-align: center;
}
@media (max-width: 600px) {
  .subs {
    padding: 16px 12px;
  }
}
</style>