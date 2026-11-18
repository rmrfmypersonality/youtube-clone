<script setup>
import { computed, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { api } from '../api/client'
import { formatComments } from '../composables/format'
import { useAuth } from '../composables/useAuth'
import { usePagedList } from '../composables/usePagedList'
import AppIcon from './AppIcon.vue'
import CommentItem from './CommentItem.vue'
import InfiniteScroll from './InfiniteScroll.vue'

const props = defineProps({ videoId: { type: Number, required: true } })

// Пункты меню «Упорядочить» (value уходит в API как sort)
const SORT_OPTIONS = [
  { value: 'popular', label: 'Сначала популярные', hint: 'Показать избранные комментарии' },
  {
    value: 'new',
    label: 'Новые',
    hint: 'Показать последние комментарии, включая потенциальный спам',
  },
]

const route = useRoute()
const { state: auth } = useAuth()

const sort = ref('popular')
const menuOpen = ref(false)
const text = ref('')
const posting = ref(false)
const postError = ref('')
const total = ref(null)

const heading = computed(() => (total.value === null ? 'Комментарии' : formatComments(total.value)))

const { items, loading, done, error, loadMore, reset } = usePagedList((cursor) =>
  api.comments.list(props.videoId, sort.value, cursor),
)

async function loadCount() {
  try {
    total.value = (await api.comments.count(props.videoId)).count
  } catch {
    /* счётчик не критичен */
  }
}
loadCount()

watch(sort, () => {
  reset()
  loadMore()
})

function choose(value) {
  menuOpen.value = false
  sort.value = value
}

async function submit() {
  const value = text.value.trim()
  if (!value || posting.value) return
  posting.value = true
  postError.value = ''
  try {
    const created = await api.comments.create(props.videoId, { text: value })
    text.value = ''
    // Новый комментарий самый свежий: в «новых» он первый, в «старых» последний,
    // но попадает в список только если мы уже дошли до конца (иначе подгрузится сам)
    items.value.unshift(created)
    loadCount()
  } catch (e) {
    postError.value = e.message
  } finally {
    posting.value = false
  }
}

function onDeleted(id) {
  items.value = items.value.filter((c) => c.id !== id)
  loadCount() // у корневого уходят и ответы: пересчитываем на сервере
}
</script>

<template>
  <section class="comments">
    <div class="top">
      <h2>{{ heading }}</h2>
      <div class="sort">
        <button type="button" class="sort-btn" aria-haspopup="true" @click="menuOpen = !menuOpen">
          <AppIcon name="sort" :size="24" />
          <span>Упорядочить</span>
        </button>
        <div v-if="menuOpen" class="backdrop" @click="menuOpen = false" />
        <div v-if="menuOpen" class="menu" role="menu">
          <button
            v-for="o in SORT_OPTIONS"
            :key="o.value"
            type="button"
            role="menuitem"
            class="option"
            :class="{ active: sort === o.value }"
            @click="choose(o.value)"
          >
            <span class="label">{{ o.label }}</span>
            <span class="hint">{{ o.hint }}</span>
          </button>
        </div>
      </div>
    </div>

    <form v-if="auth.user" class="form" @submit.prevent="submit">
      <label class="field">
        <textarea v-model="text" maxlength="2000" placeholder="Добавьте комментарий" required />
      </label>
      <p v-if="postError" class="error" role="alert">{{ postError }}</p>
      <button class="btn btn-primary" :disabled="posting || !text.trim()">Отправить</button>
    </form>
    <p v-else class="muted">
      <RouterLink :to="{ name: 'login', query: { next: route.fullPath } }">Войдите</RouterLink>,
      чтобы оставить комментарий.
    </p>

    <div class="list">
      <CommentItem
        v-for="comment in items"
        :key="comment.id"
        :comment="comment"
        :video-id="videoId"
        @deleted="onDeleted"
        @changed="loadCount"
      />
    </div>
    <p v-if="done && !items.length" class="muted">Комментариев пока нет</p>
    <InfiniteScroll :loading="loading" :done="done" :error="error" @load="loadMore" />
  </section>
</template>

<style scoped>
.comments {
  margin-top: 24px;
}
.top {
  display: flex;
  gap: 32px;
  align-items: center;
  margin-bottom: 16px;
}
h2 {
  margin: 0;
  font-size: 20px;
  font-weight: 600;
}
.sort {
  position: relative;
}
.sort-btn {
  display: flex;
  gap: 8px;
  align-items: center;
  padding: 0;
  border: none;
  background: none;
  color: var(--text);
  font: inherit;
  font-weight: 500;
  cursor: pointer;
}
.backdrop {
  position: fixed;
  inset: 0;
  z-index: 10;
}
.menu {
  position: absolute;
  top: 36px;
  left: 0;
  z-index: 11;
  min-width: 300px;
  padding: 8px 0;
  border-radius: var(--radius);
  background: var(--surface);
  box-shadow: 0 4px 32px rgba(0, 0, 0, 0.4);
}
.option {
  display: block;
  width: 100%;
  padding: 10px 16px;
  border: none;
  background: none;
  color: var(--text);
  font: inherit;
  text-align: left;
  cursor: pointer;
}
.option:hover,
.option.active {
  background: var(--surface-hover);
}
.label {
  display: block;
  font-weight: 500;
}
.hint {
  display: block;
  color: var(--text-secondary);
  font-size: 13px;
}
.form {
  margin-bottom: 24px;
}
.list {
  display: flex;
  flex-direction: column;
  gap: 20px;
}
</style>