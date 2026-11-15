<script setup>
import { computed, watch } from 'vue'
import { useRoute } from 'vue-router'
import { api } from '../api/client'
import InfiniteScroll from '../components/InfiniteScroll.vue'
import VideoCard from '../components/VideoCard.vue'
import { usePagedList } from '../composables/usePagedList'

const route = useRoute()
const q = computed(() => String(route.query.q ?? '').trim())

const { items, loading, done, error, loadMore, reset } = usePagedList((cursor) =>
  api.search(q.value, cursor),
)

watch(
  q,
  () => {
    reset()
    if (q.value) loadMore()
  },
  { immediate: true },
)
</script>

<template>
  <div class="search">
    <p v-if="!q" class="muted">Введите запрос в поле поиска</p>
    <template v-else>
      <VideoCard v-for="video in items" :key="video.id" :video="video" horizontal />
      <p v-if="done && !items.length" class="muted">Ничего не найдено</p>
      <InfiniteScroll :loading="loading" :done="done" :error="error" @load="loadMore" />
    </template>
  </div>
</template>

<style scoped>
.search {
  display: flex;
  flex-direction: column;
  gap: 16px;
  max-width: 1000px;
  margin: 0 auto;
  padding: 24px 16px;
}
</style>