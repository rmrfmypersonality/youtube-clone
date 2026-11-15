<script setup>
import { ref, watch } from 'vue'
import { api } from '../api/client'
import InfiniteScroll from '../components/InfiniteScroll.vue'
import { formatRelative } from '../composables/format'
import { REPORT_REASONS } from '../composables/moderation'
import { usePagedList } from '../composables/usePagedList'

const TABS = [
  ['open', 'Открытые'],
  ['resolved', 'Обработанные'],
  ['dismissed', 'Отклонённые'],
]
const VISIBILITY = {
  public: 'Открытый доступ',
  unlisted: 'Доступ по ссылке',
  private: 'Ограниченный доступ',
}

const status = ref('open')
const { items, loading, done, error, loadMore, reset } = usePagedList((cursor) =>
  api.moderation.reports(status.value, cursor),
)
const actionError = ref('')
const busyId = ref(null)

watch(
  status,
  () => {
    reset()
    loadMore()
  },
  { immediate: true },
)

const targetOf = (report) => report.video ?? report.comment

function toggleLabel(report) {
  const hidden = targetOf(report).hidden
  if (report.video) return hidden ? 'Вернуть видео' : 'Скрыть видео'
  return hidden ? 'Вернуть комментарий' : 'Скрыть комментарий'
}

// После скрытия сервер закрывает все открытые жалобы на цель: убираем их из очереди
function applyHidden(kind, id, hidden) {
  for (const r of items.value) {
    if (r[kind]?.id === id) r[kind].hidden = hidden
  }
  if (hidden && status.value === 'open') {
    items.value = items.value.filter((r) => r[kind]?.id !== id)
  }
}

async function toggleHidden(report) {
  const kind = report.video ? 'video' : 'comment'
  const target = report[kind]
  const hide = !target.hidden
  busyId.value = report.id
  actionError.value = ''
  try {
    if (kind === 'video') {
      await (hide ? api.moderation.hideVideo(target.id) : api.moderation.unhideVideo(target.id))
    } else {
      await (hide ? api.moderation.hideComment(target.id) : api.moderation.unhideComment(target.id))
    }
    applyHidden(kind, target.id, hide)
  } catch (e) {
    actionError.value = e.message
  } finally {
    busyId.value = null
  }
}

async function dismiss(report) {
  busyId.value = report.id
  actionError.value = ''
  try {
    await api.moderation.dismiss(report.id)
    items.value = items.value.filter((r) => r.id !== report.id)
  } catch (e) {
    actionError.value = e.message
  } finally {
    busyId.value = null
  }
}
</script>

<template>
  <div class="mod">
    <h1>Модерация</h1>
    <nav class="tabs">
      <button
        v-for="[value, label] in TABS"
        :key="value"
        type="button"
        class="tab"
        :class="{ active: status === value }"
        @click="status = value"
      >
        {{ label }}
      </button>
    </nav>
    <p v-if="actionError" class="error" role="alert">{{ actionError }}</p>

    <article v-for="r in items" :key="r.id" class="report">
      <div class="head">
        <strong>{{ REPORT_REASONS[r.reason] ?? r.reason }}</strong>
        <span class="muted">от @{{ r.reporter?.handle }} • {{ formatRelative(r.created_at) }}</span>
      </div>
      <p v-if="r.details" class="details">{{ r.details }}</p>

      <div v-if="r.video" class="target">
        <div class="kind">Видео</div>
        <div class="title">{{ r.video.title }}</div>
        <div class="muted">@{{ r.video.owner?.handle }} • {{ VISIBILITY[r.video.visibility] }}</div>
        <div v-if="r.video.hidden" class="hidden">Скрыто</div>
        <RouterLink v-if="r.video.visibility !== 'private'" :to="`/watch/${r.video.id}`">
          Открыть видео
        </RouterLink>
        <div v-else class="muted">Ограниченный доступ: содержимое модератору недоступно</div>
      </div>

      <div v-else-if="r.comment" class="target">
        <div class="kind">Комментарий</div>
        <p class="quote">{{ r.comment.text }}</p>
        <div class="muted">@{{ r.comment.author?.handle }}</div>
        <div v-if="r.comment.hidden" class="hidden">Скрыто</div>
        <RouterLink :to="`/watch/${r.comment.video_id}`">К видео</RouterLink>
      </div>

      <div v-if="r.handled_by" class="muted">
        Обработал @{{ r.handled_by.handle }} • {{ formatRelative(r.handled_at) }}
      </div>

      <div class="actions">
        <template v-if="r.status === 'open'">
          <button
            type="button"
            class="btn btn-primary"
            :disabled="busyId === r.id"
            @click="toggleHidden(r)"
          >
            {{ toggleLabel(r) }}
          </button>
          <button type="button" class="btn" :disabled="busyId === r.id" @click="dismiss(r)">
            Отклонить жалобу
          </button>
        </template>
        <button
          v-else-if="targetOf(r)?.hidden"
          type="button"
          class="btn"
          :disabled="busyId === r.id"
          @click="toggleHidden(r)"
        >
          {{ toggleLabel(r) }}
        </button>
      </div>
    </article>

    <p v-if="done && !items.length" class="muted">Здесь пока пусто</p>
    <InfiniteScroll :loading="loading" :done="done" :error="error" @load="loadMore" />
  </div>
</template>

<style scoped>
.mod {
  max-width: 800px;
  margin: 0 auto;
  padding: 24px 16px;
}
h1 {
  margin: 0 0 16px;
  font-size: 22px;
  font-weight: 500;
}
.tabs {
  display: flex;
  gap: 8px;
  margin-bottom: 16px;
  border-bottom: 1px solid var(--border);
}
.tab {
  padding: 10px 20px;
  border: none;
  border-bottom: 2px solid transparent;
  background: none;
  color: var(--text-secondary);
  font: inherit;
  font-weight: 500;
  cursor: pointer;
}
.tab.active {
  border-bottom-color: var(--text);
  color: var(--text);
}
.report {
  margin-bottom: 16px;
  padding: 16px;
  border-radius: var(--radius);
  background: var(--surface);
}
.head {
  display: flex;
  flex-wrap: wrap;
  gap: 4px 12px;
  align-items: baseline;
}
.details {
  margin: 8px 0;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}
.target {
  margin: 12px 0;
  padding: 12px;
  border-radius: 8px;
  background: var(--bg);
}
.kind {
  color: var(--text-secondary);
  font-size: 12px;
  text-transform: uppercase;
}
.title {
  font-weight: 500;
  overflow-wrap: anywhere;
}
.quote {
  margin: 4px 0;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}
.hidden {
  color: var(--danger);
}
.actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 12px;
}
</style>