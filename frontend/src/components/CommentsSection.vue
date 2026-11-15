<script setup>
import { ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { api } from '../api/client'
import { useAuth } from '../composables/useAuth'
import { usePagedList } from '../composables/usePagedList'
import CommentItem from './CommentItem.vue'
import InfiniteScroll from './InfiniteScroll.vue'

const props = defineProps({ videoId: { type: Number, required: true } })

const route = useRoute()
const { state: auth } = useAuth()

const sort = ref('new')
const text = ref('')
const posting = ref(false)
const postError = ref('')

const { items, loading, done, error, loadMore, reset } = usePagedList((cursor) =>
  api.comments.list(props.videoId, sort.value, cursor),
)

watch(sort, () => {
  reset()
  loadMore()
})

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
    if (sort.value === 'new') items.value.unshift(created)
    else if (done.value) items.value.push(created)
  } catch (e) {
    postError.value = e.message
  } finally {
    posting.value = false
  }
}

function onDeleted(id) {
  items.value = items.value.filter((c) => c.id !== id)
}
</script>

<template>
  <section class="comments">
    <div class="top">
      <h2>Комментарии</h2>
      <select v-model="sort" aria-label="Сортировка">
        <option value="new">Сначала новые</option>
        <option value="old">Сначала старые</option>
      </select>
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
  gap: 16px;
  align-items: center;
  margin-bottom: 16px;
}
h2 {
  margin: 0;
  font-size: 20px;
  font-weight: 600;
}
select {
  padding: 6px 8px;
  border: 1px solid var(--border);
  border-radius: 8px;
  background: var(--bg);
  color: var(--text);
  font: inherit;
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