<script setup>
import { computed, ref } from 'vue'
import { api } from '../api/client'
import { formatRelative } from '../composables/format'
import { useAuth } from '../composables/useAuth'
import { usePagedList } from '../composables/usePagedList'
import ReportDialog from './ReportDialog.vue'
import { useRoute, useRouter } from 'vue-router'
import AppIcon from './AppIcon.vue'

const props = defineProps({
  comment: { type: Object, required: true },
  videoId: { type: Number, required: true },
  reply: Boolean, // ответ: без своей ветки и кнопки «Ответить»
})
const emit = defineEmits(['deleted', 'changed'])

const { state: auth, isModerator } = useAuth()
const route = useRoute()
const router = useRouter()

const likes = ref(props.comment.likes_count)
const mine = ref(props.comment.my_reaction)
const reacting = ref(false)

async function react(value) {
  if (!auth.user) {
    router.push({ name: 'login', query: { next: route.fullPath } })
    return
  }
  if (reacting.value) return
  reacting.value = true
  actionError.value = ''
  try {
    const next = mine.value === value ? 0 : value // повторный клик снимает реакцию
    const res = await api.comments.react(props.comment.id, next)
    likes.value = res.likes_count
    mine.value = res.my_reaction
  } catch (e) {
    actionError.value = e.message
  } finally {
    reacting.value = false
  }
}

// Сервер всё равно проверит: это только чтобы не показывать лишних кнопок
const canDelete = computed(
  () => !!auth.user && (auth.user.id === props.comment.author.id || auth.user.role === 'admin'),
)

const actionError = ref('')

const isAuthor = computed(() => auth.user?.id === props.comment.author.id)
const hidden = ref(props.comment.hidden_by_moderation)
const reportOpen = ref(false)
const moderating = ref(false)

async function toggleHidden() {
  moderating.value = true
  actionError.value = ''
  try {
    const res = hidden.value
      ? await api.moderation.unhideComment(props.comment.id)
      : await api.moderation.hideComment(props.comment.id)
    hidden.value = res.hidden
  } catch (e) {
    actionError.value = e.message
  } finally {
    moderating.value = false
  }
}

async function remove() {
  if (!confirm('Удалить комментарий?')) return
  actionError.value = ''
  try {
    await api.comments.remove(props.comment.id)
    emit('deleted', props.comment.id)
  } catch (e) {
    actionError.value = e.message
  }
}

// --- ответы (только у корневых комментариев) ---
const replyCount = ref(props.comment.reply_count)
const open = ref(false)
const {
  items: replyItems,
  loading: repliesLoading,
  done: repliesDone,
  error: repliesError,
  loadMore: loadReplies,
  reset: resetReplies,
} = usePagedList((cursor) => api.comments.replies(props.comment.id, cursor))

function toggleReplies() {
  open.value = !open.value
  if (open.value && !replyItems.value.length && !repliesDone.value) loadReplies()
}

function onReplyDeleted(id) {
  replyItems.value = replyItems.value.filter((r) => r.id !== id)
  replyCount.value--
  emit('changed')
}

const replying = ref(false)
const replyText = ref('')
const posting = ref(false)
const replyError = ref('')

async function sendReply() {
  const text = replyText.value.trim()
  if (!text || posting.value) return
  posting.value = true
  replyError.value = ''
  try {
    const created = await api.comments.create(props.videoId, { text, parent_id: props.comment.id })
    replyText.value = ''
    replying.value = false
    replyCount.value++
    emit('changed')
    if (open.value && repliesDone.value) {
      replyItems.value.push(created)
    } else {
      // Часть ответов ещё не загружена: перечитываем ветку с начала, чтобы не получить дубль
      resetReplies()
      open.value = true
      await loadReplies()
    }
  } catch (e) {
    replyError.value = e.message
  } finally {
    posting.value = false
  }
}
</script>

<template>
  <div class="comment" :class="{ reply }">
    <span class="avatar">{{ comment.author.name[0]?.toUpperCase() }}</span>
    <div class="body">
      <div class="head">
        <strong>@{{ comment.author.handle }}</strong>
        <span class="muted">{{ formatRelative(comment.created_at) }}</span>
      </div>
      <p class="text">{{ comment.text }}</p>
      <p v-if="hidden" class="hidden-note">Скрыт модератором</p>

      <div class="row">
        <div class="react">
          <button
            type="button"
            class="react-btn"
            :class="{ active: mine === 1 }"
            :aria-pressed="mine === 1"
            aria-label="Нравится"
            :disabled="reacting"
            @click="react(1)"
          >
            <AppIcon name="like" :size="18" />
            <span v-if="likes > 0">{{ likes }}</span>
          </button>
          <button
            type="button"
            class="react-btn"
            :class="{ active: mine === -1 }"
            :aria-pressed="mine === -1"
            aria-label="Не нравится"
            :disabled="reacting"
            @click="react(-1)"
          >
            <AppIcon name="dislike" :size="18" />
          </button>
        </div>
        <button v-if="!reply && auth.user" type="button" class="link" @click="replying = !replying">
          Ответить
        </button>
        <button v-if="canDelete" type="button" class="link" @click="remove">Удалить</button>
        <button
          v-if="auth.user && !isAuthor"
          type="button"
          class="link"
          @click="reportOpen = true"
        >
          Пожаловаться
        </button>
        <button
          v-if="isModerator"
          type="button"
          class="link"
          :disabled="moderating"
          @click="toggleHidden"
        >
          {{ hidden ? 'Вернуть' : 'Скрыть' }}
        </button>
      </div>
      <p v-if="actionError" class="error" role="alert">{{ actionError }}</p>

      <form v-if="replying" class="reply-form" @submit.prevent="sendReply">
        <label class="field">
          <textarea v-model="replyText" maxlength="2000" placeholder="Добавьте ответ" required />
        </label>
        <p v-if="replyError" class="error" role="alert">{{ replyError }}</p>
        <div class="row">
          <button type="button" class="btn" @click="replying = false">Отмена</button>
          <button class="btn btn-primary" :disabled="posting || !replyText.trim()">Ответить</button>
        </div>
      </form>

      <button v-if="!reply && replyCount > 0" type="button" class="link toggle" @click="toggleReplies">
        {{ open ? 'Скрыть ответы' : `Ответов: ${replyCount}` }}
      </button>

      <div v-if="open" class="replies">
        <CommentItem
          v-for="r in replyItems"
          :key="r.id"
          :comment="r"
          :video-id="videoId"
          reply
          @deleted="onReplyDeleted"
        />
        <p v-if="repliesLoading" class="muted">Загрузка…</p>
        <p v-if="repliesError" class="error" role="alert">{{ repliesError }}</p>
        <button
          v-if="!repliesDone && !repliesLoading"
          type="button"
          class="link"
          @click="loadReplies"
        >
          Показать ещё
        </button>
      </div>
      <ReportDialog
        v-if="reportOpen"
        kind="comment"
        :target-id="comment.id"
        @close="reportOpen = false"
      />
    </div>
  </div>
</template>

<style scoped>
.comment {
  display: flex;
  gap: 12px;
}
.avatar {
  display: grid;
  flex: none;
  place-items: center;
  width: 40px;
  height: 40px;
  border-radius: 50%;
  background: var(--link);
  color: var(--on-link);
  font-weight: 500;
}
.reply .avatar {
  width: 24px;
  height: 24px;
  font-size: 12px;
}
.body {
  flex: 1;
  min-width: 0;
}
.head {
  display: flex;
  gap: 8px;
  align-items: baseline;
}
.text {
  margin: 2px 0 6px;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}
.row {
  display: flex;
  gap: 16px;
  align-items: center;
}
.reply-form {
  margin-top: 8px;
}
.reply-form .row {
  justify-content: flex-end;
  gap: 8px;
}
.toggle {
  display: block;
  margin-top: 6px;
}
.replies {
  display: flex;
  flex-direction: column;
  gap: 16px;
  margin-top: 12px;
}
.hidden-note {
  margin: 0 0 6px;
  color: var(--danger);
}
.react {
  display: flex;
  gap: 4px;
  align-items: center;
}
.react-btn {
  display: inline-flex;
  gap: 6px;
  align-items: center;
  min-height: 32px;
  padding: 0 8px;
  border: none;
  border-radius: 16px;
  background: none;
  color: var(--text);
  font: inherit;
  cursor: pointer;
  transition: background 0.15s;
}
.react-btn:hover {
  background: var(--surface);
}
.react-btn.active {
  color: var(--link);
}
.react-btn:disabled {
  opacity: 0.6;
  cursor: default;
}
</style>