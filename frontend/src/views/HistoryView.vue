<script setup>
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { api } from '../api/client'
import AppIcon from '../components/AppIcon.vue'
import InfiniteScroll from '../components/InfiniteScroll.vue'
import VideoCard from '../components/VideoCard.vue'
import { usePagedList } from '../composables/usePagedList'

const search = ref('')
const query = ref('') // применённый запрос (после паузы ввода)
const { items, loading, done, error, loadMore, reset } = usePagedList((cursor) =>
  api.history.list(cursor, query.value || undefined),
)
const actionError = ref('')
let timer = null

onMounted(() => {
  document.title = 'История просмотра — YouTube Clone'
})
onBeforeUnmount(() => clearTimeout(timer))

// Поиск срабатывает после паузы в 300 мс, чтобы не слать запрос на каждую букву
watch(search, (value) => {
  clearTimeout(timer)
  timer = setTimeout(() => {
    const next = value.trim()
    if (next === query.value) return
    query.value = next
    reset()
    loadMore()
  }, 300)
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
  if (!confirm('Очистить всю историю просмотра? Будет удалена вся история, а не только найденное.')) {
    return
  }
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
    <div class="main">
      <h1>История просмотра</h1>
      <p v-if="actionError" class="error" role="alert">{{ actionError }}</p>

      <VideoCard
        v-for="video in items"
        :key="video.id"
        :video="video"
        horizontal
        class="item"
        remove-label="Удалить из истории просмотра"
        @remove="remove"
      />

      <p v-if="done && !items.length" class="muted">
        {{ query ? 'Ничего не найдено' : 'История просмотра пуста' }}
      </p>
      <InfiniteScroll :loading="loading" :done="done" :error="error" @load="loadMore" />
    </div>

    <aside class="side">
      <label class="search">
        <AppIcon name="search" :size="24" />
        <input
          v-model="search"
          type="search"
          maxlength="100"
          placeholder="Искать в истории просмотра"
          aria-label="Поиск в истории просмотра"
        />
      </label>
      <button type="button" class="clear" @click="clearAll">
        <AppIcon name="delete" :size="24" />
        <span>Очистить историю просмотра</span>
      </button>
    </aside>
  </div>
</template>

<style scoped>
.history {
  display: flex;
  gap: 32px;
  align-items: flex-start;
  max-width: 1300px;
  margin: 0 auto;
  padding: 24px 16px;
}
.main {
  flex: 1;
  min-width: 0;
}
h1 {
  margin: 0 0 16px;
  font-size: 22px;
  font-weight: 500;
}
.item {
  margin-bottom: 16px;
}
.side {
  position: sticky;
  top: calc(var(--header-height) + 24px);
  flex: 0 0 320px;
  width: 320px;
}
.search {
  display: flex;
  gap: 12px;
  align-items: center;
  padding-bottom: 6px;
  border-bottom: 1px solid var(--text-secondary);
  color: var(--text);
}
.search:focus-within {
  border-bottom-color: var(--text);
}
.search input {
  flex: 1;
  min-width: 0;
  padding: 6px 0;
  border: none;
  background: transparent;
  color: var(--text);
  font: inherit;
  font-size: 16px;
}
.search input:focus {
  outline: none;
}
.clear {
  display: flex;
  gap: 12px;
  align-items: center;
  margin-top: 32px;
  padding: 0;
  border: none;
  background: none;
  color: var(--text);
  font: inherit;
  font-weight: 500;
  cursor: pointer;
}
.clear:hover {
  color: var(--link);
}
@media (max-width: 900px) {
  .history {
    flex-direction: column-reverse;
    align-items: stretch;
    gap: 16px;
    padding: 16px 12px;
  }
  .side {
    position: static;
    flex: none;
    width: auto;
  }
}
</style>