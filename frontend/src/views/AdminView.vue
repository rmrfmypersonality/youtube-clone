<script setup>
import { ref, watch } from 'vue'
import { api } from '../api/client'
import InfiniteScroll from '../components/InfiniteScroll.vue'
import { formatRelative } from '../composables/format'
import { useAuth } from '../composables/useAuth'
import { usePagedList } from '../composables/usePagedList'

const ACTION_LABELS = {
  'report.dismiss': 'Отклонил жалобу',
  'video.hide': 'Скрыл видео',
  'video.unhide': 'Вернул видео',
  'video.update': 'Изменил чужое видео',
  'video.delete': 'Удалил чужое видео',
  'comment.hide': 'Скрыл комментарий',
  'comment.unhide': 'Вернул комментарий',
  'comment.delete': 'Удалил чужой комментарий',
  'playlist.update': 'Изменил чужой плейлист',
  'playlist.delete': 'Удалил чужой плейлист',
  'user.role_change': 'Сменил роль',
  'user.block': 'Заблокировал',
  'user.unblock': 'Разблокировал',
}
const ROLES = { user: 'Пользователь', moderator: 'Модератор', admin: 'Администратор' }

const { state: auth } = useAuth()
const tab = ref('users')
const actionError = ref('')

// --- пользователи ---
const search = ref('')
const query = ref('')
const {
  items: users,
  loading: usersLoading,
  done: usersDone,
  error: usersError,
  loadMore: loadUsers,
  reset: resetUsers,
} = usePagedList((cursor) => api.admin.users(query.value, cursor))

watch(query, () => {
  resetUsers()
  loadUsers()
})

function applySearch() {
  query.value = search.value.trim()
}

const isSelf = (u) => u.id === auth.user?.id

async function changeRole(u, event) {
  actionError.value = ''
  try {
    Object.assign(u, await api.admin.updateUser(u.id, { role: event.target.value }))
  } catch (e) {
    actionError.value = e.message
    event.target.value = u.role // откатываем выбор в select
  }
}

async function toggleBlock(u) {
  if (u.is_active && !confirm(`Заблокировать @${u.username}?`)) return
  actionError.value = ''
  try {
    Object.assign(u, await api.admin.updateUser(u.id, { is_active: !u.is_active }))
  } catch (e) {
    actionError.value = e.message
  }
}

// --- журнал ---
const {
  items: entries,
  loading: auditLoading,
  done: auditDone,
  error: auditError,
  loadMore: loadAudit,
} = usePagedList((cursor) => api.admin.audit(cursor))
</script>

<template>
  <div class="admin">
    <h1>Администрирование</h1>
    <nav class="tabs">
      <button type="button" class="tab" :class="{ active: tab === 'users' }" @click="tab = 'users'">
        Пользователи
      </button>
      <button type="button" class="tab" :class="{ active: tab === 'audit' }" @click="tab = 'audit'">
        Журнал действий
      </button>
    </nav>
    <p v-if="actionError" class="error" role="alert">{{ actionError }}</p>

    <section v-if="tab === 'users'">
      <form class="search" @submit.prevent="applySearch">
        <input v-model="search" maxlength="100" placeholder="Имя пользователя или email" />
        <button class="btn">Найти</button>
      </form>

      <div v-for="u in users" :key="u.id" class="user" :class="{ blocked: !u.is_active }">
        <div class="who">
          <RouterLink :to="`/@${u.channel_handle}`">@{{ u.username }}</RouterLink>
          <span v-if="isSelf(u)" class="muted"> (вы)</span>
          <div class="muted">{{ u.email }}</div>
          <div v-if="!u.is_active" class="danger">Заблокирован</div>
        </div>
        <select :value="u.role" :disabled="isSelf(u)" @change="changeRole(u, $event)">
          <option v-for="(label, value) in ROLES" :key="value" :value="value">{{ label }}</option>
        </select>
        <button type="button" class="btn" :disabled="isSelf(u)" @click="toggleBlock(u)">
          {{ u.is_active ? 'Заблокировать' : 'Разблокировать' }}
        </button>
      </div>

      <p v-if="usersDone && !users.length" class="muted">Никого не найдено</p>
      <InfiniteScroll
        :loading="usersLoading"
        :done="usersDone"
        :error="usersError"
        @load="loadUsers"
      />
    </section>

    <section v-else>
      <div v-for="a in entries" :key="a.id" class="entry">
        <div>
          <strong>@{{ a.actor?.handle ?? 'удалён' }}</strong>
          {{ ACTION_LABELS[a.action] ?? a.action }}
          <span class="muted">({{ a.target_type }} #{{ a.target_id }})</span>
        </div>
        <div v-if="a.details" class="muted details">{{ JSON.stringify(a.details) }}</div>
        <div class="muted">{{ formatRelative(a.created_at) }}</div>
      </div>
      <p v-if="auditDone && !entries.length" class="muted">Журнал пуст</p>
      <InfiniteScroll
        :loading="auditLoading"
        :done="auditDone"
        :error="auditError"
        @load="loadAudit"
      />
    </section>
  </div>
</template>

<style scoped>
.admin {
  max-width: 900px;
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
.search {
  display: flex;
  gap: 8px;
  max-width: 520px;
  margin-bottom: 16px;
}
.search input {
  flex: 1;
  min-width: 0;
  padding: 0 14px;
  height: 36px;
  border: 1px solid var(--border);
  border-radius: 18px;
  background: var(--bg);
  color: var(--text);
  font: inherit;
}
.user {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  align-items: center;
  margin-bottom: 8px;
  padding: 12px 16px;
  border-radius: var(--radius);
  background: var(--surface);
}
.user.blocked {
  opacity: 0.75;
}
.who {
  flex: 1;
  min-width: 200px;
  overflow-wrap: anywhere;
}
.danger {
  color: var(--danger);
}
select {
  padding: 6px 8px;
  border: 1px solid var(--border);
  border-radius: 8px;
  background: var(--bg);
  color: var(--text);
  font: inherit;
}
.entry {
  margin-bottom: 8px;
  padding: 12px 16px;
  border-radius: var(--radius);
  background: var(--surface);
}
.details {
  overflow-wrap: anywhere;
}
</style>