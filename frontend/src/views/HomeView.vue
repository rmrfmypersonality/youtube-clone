<script setup>
import { computed, watch } from 'vue'
import { useRoute } from 'vue-router'
import { api } from '../api/client'
import ChipBar from '../components/ChipBar.vue'
import InfiniteScroll from '../components/InfiniteScroll.vue'
import VideoCard from '../components/VideoCard.vue'
import { usePagedList } from '../composables/usePagedList'

const route = useRoute()
const category = computed(() => String(route.query.category ?? '') || null)

const { items, loading, done, error, loadMore, reset } = usePagedList((cursor) =>
  api.videos.list(cursor, category.value),
)

// Смена категории: сбрасываем ленту и грузим заново
watch(category, () => {
  reset()
  loadMore()
})
</script>

<template>
  <div>
    <ChipBar />
    <div class="content">
      <div class="video-grid">
        <VideoCard v-for="video in items" :key="video.id" :video="video" />
      </div>
      <p v-if="done && !items.length" class="muted empty">
        {{ category ? 'В этой категории пока нет видео' : 'Пока нет ни одного видео' }}
      </p>
      <InfiniteScroll :loading="loading" :done="done" :error="error" @load="loadMore" />
    </div>
  </div>
</template>

<style scoped>
.content {
  padding: 8px 24px 24px;
}
.empty {
  text-align: center;
}
@media (max-width: 600px) {
  .content {
    padding: 8px 12px 24px;
  }
}
</style>