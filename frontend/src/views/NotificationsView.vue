<script setup>
import { onMounted } from 'vue'
import { api } from '../api/client'
import InfiniteScroll from '../components/InfiniteScroll.vue'
import VideoCard from '../components/VideoCard.vue'
import { useNotifications } from '../composables/useNotifications'
import { usePagedList } from '../composables/usePagedList'

const { markSeen } = useNotifications()

// seen_at из ПЕРВОЙ страницы: по нему подсвечиваем новое. Потом страница сама отмечает
// уведомления прочитанными, и seen_at в следующих ответах уже новый.
let previousSeen = null

const { items, loading, done, error, loadMore } = usePagedList(async (cursor) => {
  const page = await api.notifications.list(cursor)
  if (previousSeen === null) {
    previousSeen = page.seen_at
    markSeen().catch(() => {}) // запрос уходит после ответа списка, так что гонки нет
  }
  return page
})

const isNew = (video) => previousSeen !== null && new Date(video.published_at) > new Date(previousSeen)

onMounted(() => {
  document.title = 'Уведомления — YouTube Clone'
})
</script>

<template>
  <div class="notifications">
    <h1>Уведомления</h1>
    <div v-for="video in items" :key="video.id" class="item" :class="{ fresh: isNew(video) }">
      <span v-if="isNew(video)" class="dot" aria-label="Новое" />
      <VideoCard :video="video" horizontal class="card" />
    </div>
    <p v-if="done && !items.length" class="muted">
      Здесь появятся новые видео каналов, на которые вы подписаны.
    </p>
    <InfiniteScroll :loading="loading" :done="done" :error="error" @load="loadMore" />
  </div>
</template>

<style scoped>
.notifications {
  max-width: 1000px;
  margin: 0 auto;
  padding: 24px 16px;
}
h1 {
  margin: 0 0 16px;
  font-size: 22px;
  font-weight: 500;
}
.item {
  display: flex;
  gap: 12px;
  align-items: flex-start;
  margin-bottom: 16px;
  padding: 8px;
  border-radius: var(--radius);
}
.item.fresh {
  background: var(--surface);
}
.dot {
  flex: none;
  width: 8px;
  height: 8px;
  margin-top: 8px;
  border-radius: 50%;
  background: var(--link);
}
.card {
  flex: 1;
  min-width: 0;
}
</style>