<script setup>
import { onMounted, ref } from 'vue'
import { api } from '../api/client'
import AppIcon from '../components/AppIcon.vue'
import InfiniteScroll from '../components/InfiniteScroll.vue'
import VideoCard from '../components/VideoCard.vue'
import { usePagedList } from '../composables/usePagedList'

const { items, loading, done, error, loadMore, reset } = usePagedList((cursor) =>
  api.history.list(cursor),
)
const actionError = ref('')

onMounted(() => {
  document.title = 'История просмотра — YouTube Clone'
})

async function remove(video) {
  actionError.value = ''
  try {
    await api.history.remove(video.id)
    items.value = items.value.filter((v) => v.id !== video.id)
  } catch (e) {
    actionError.value = e.message
  }
}

async function clearAll() {
  if (!confirm('Очистить всю историю просмотра?')) return
  actionError.value = ''
  try {
    await api.history.clear()
    reset()
    await loadMore() // пустая страница выставит done
  } catch (e) {
    actionError.value = e.message
  }
}
</script>

<template>
  <div class="history">
    <div class="top">
      <h1>История просмотра</h1>
      <button v-if="items.length" type="button" class="btn" @click="clearAll">
        Очистить историю
      </button>
    </div>
    <p v-if="actionError" class="error" role="alert">{{ actionError }}</p>

    <div v-for="video in items" :key="video.id" class="item">
      <VideoCard :video="video" horizontal class="card" />
      <button
        type="button"
        class="icon-btn"
        aria-label="Убрать из истории"
        @click="remove(video)"
      >
        <AppIcon name="close" :size="20" />
      </button>
    </div>

    <p v-if="done && !items.length" class="muted">История просмотра пуста</p>
    <InfiniteScroll :loading="loading" :done="done" :error="error" @load="loadMore" />
  </div>
</template>

<style scoped>
.history {
  max-width: 1000px;
  margin: 0 auto;
  padding: 24px 16px;
}
.top {
  display: flex;
  gap: 16px;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;
}
h1 {
  margin: 0;
  font-size: 22px;
  font-weight: 500;
}
.item {
  display: flex;
  gap: 8px;
  align-items: flex-start;
  margin-bottom: 16px;
}
.card {
  flex: 1;
  min-width: 0;
}
</style>