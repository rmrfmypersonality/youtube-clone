<script setup>
import { ref } from 'vue'
import { api } from '../api/client'
import InfiniteScroll from '../components/InfiniteScroll.vue'
import VideoEditForm from '../components/VideoEditForm.vue'
import { formatDuration, formatRelative, formatViews } from '../composables/format'
import { usePagedList } from '../composables/usePagedList'

const STATUS = {
  pending: 'Файл не загружен (запись удалится через сутки)',
  uploaded: 'В очереди на обработку',
  processing: 'Обрабатывается',
  ready: 'Готово',
  failed: 'Не удалось обработать',
}
const VISIBILITY = {
  public: 'Открытый доступ',
  unlisted: 'Доступ по ссылке',
  private: 'Ограниченный доступ',
}

const { items, loading, done, error, loadMore } = usePagedList((cursor) => api.videos.mine(cursor))
const editingId = ref(null)
const actionError = ref('')

function onSaved(updated) {
  const i = items.value.findIndex((v) => v.id === updated.id)
  if (i >= 0) items.value[i] = updated
  editingId.value = null
}

async function remove(video) {
  if (!confirm(`Удалить видео «${video.title}»? Это нельзя отменить.`)) return
  actionError.value = ''
  try {
    await api.videos.remove(video.id)
    items.value = items.value.filter((v) => v.id !== video.id)
  } catch (e) {
    actionError.value = e.message
  }
}
</script>

<template>
  <div class="studio">
    <div class="top">
      <h1>Мои видео</h1>
      <RouterLink to="/upload" class="btn btn-primary">Загрузить</RouterLink>
    </div>
    <p v-if="actionError" class="error" role="alert">{{ actionError }}</p>

    <article v-for="video in items" :key="video.id" class="row">
      <div class="line">
        <div class="thumb">
          <img
            v-if="video.status === 'ready'"
            :src="`/api/videos/${video.id}/thumbnail`"
            :alt="video.title"
            loading="lazy"
          />
          <span v-if="video.status === 'ready'" class="duration">
            {{ formatDuration(video.duration_seconds) }}
          </span>
        </div>
        <div class="info">
          <div class="title">{{ video.title }}</div>
          <div class="muted">
            {{ STATUS[video.status] }} • {{ VISIBILITY[video.visibility] }}
          </div>
          <div v-if="video.hidden_by_moderation" class="hidden">Скрыто модератором</div>
          <div class="muted">
            {{ formatViews(video.views_count) }} • {{ formatRelative(video.created_at) }}
          </div>
          <div class="actions">
            <RouterLink v-if="video.status === 'ready'" :to="`/watch/${video.id}`" class="link">
              Открыть
            </RouterLink>
            <button
              type="button"
              class="link"
              @click="editingId = editingId === video.id ? null : video.id"
            >
              Изменить
            </button>
            <button type="button" class="link" @click="remove(video)">Удалить</button>
          </div>
        </div>
      </div>
      <VideoEditForm
        v-if="editingId === video.id"
        :video="video"
        @saved="onSaved"
        @cancel="editingId = null"
      />
    </article>

    <p v-if="done && !items.length" class="muted">Вы ещё не загрузили ни одного видео</p>
    <InfiniteScroll :loading="loading" :done="done" :error="error" @load="loadMore" />
  </div>
</template>

<style scoped>
.studio {
  max-width: 900px;
  margin: 0 auto;
  padding: 24px 16px;
}
.top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;
}
h1 {
  margin: 0;
  font-size: 22px;
  font-weight: 500;
}
.row {
  margin-bottom: 16px;
  padding: 12px;
  border-radius: var(--radius);
  background: var(--surface);
}
.line {
  display: flex;
  gap: 16px;
}
.thumb {
  position: relative;
  flex: none;
  width: 200px;
  aspect-ratio: 16 / 9;
  overflow: hidden;
  border-radius: 8px;
  background: var(--bg);
}
.thumb img {
  display: block;
  width: 100%;
  height: 100%;
  object-fit: cover;
}
.duration {
  position: absolute;
  right: 6px;
  bottom: 6px;
  padding: 1px 4px;
  border-radius: 4px;
  background: rgba(0, 0, 0, 0.8);
  color: #fff;
  font-size: 12px;
}
.info {
  min-width: 0;
}
.title {
  font-weight: 500;
  overflow-wrap: anywhere;
}
.hidden {
  color: var(--danger);
}
.actions {
  display: flex;
  gap: 16px;
  margin-top: 8px;
}
.actions a.link {
  display: inline-block;
}
.row > :deep(.edit) {
  margin-top: 16px;
  padding-top: 16px;
  border-top: 1px solid var(--border);
}
@media (max-width: 600px) {
  .line {
    flex-direction: column;
  }
  .thumb {
    width: 100%;
  }
}
</style>