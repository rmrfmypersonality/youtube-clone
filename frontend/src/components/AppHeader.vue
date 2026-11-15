<script setup>
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuth } from '../composables/useAuth'

const { state, logout, isModerator, isAdmin } = useAuth()
const router = useRouter()
const menuOpen = ref(false)

const ROLE_LABELS = { moderator: 'Модератор', admin: 'Администратор' }

const initial = computed(() => state.user?.username?.[0]?.toUpperCase() ?? '')
const roleLabel = computed(() => ROLE_LABELS[state.user?.role] ?? null)

const route = useRoute()
const query = ref(String(route.query.q ?? ''))

watch(
  () => route.query.q,
  (value) => {
    query.value = String(value ?? '')
  },
)

function onSearch() {
  const q = query.value.trim()
  if (q) router.push({ name: 'search', query: { q } })
}

async function onLogout() {
  menuOpen.value = false
  await logout()
  router.push('/')
}
</script>

<template>
  <header class="header">
    <RouterLink to="/" class="logo">
      <svg width="28" height="20" viewBox="0 0 28 20" aria-hidden="true">
        <rect width="28" height="20" rx="6" fill="var(--accent)" />
        <path d="M11 5.5v9l8-4.5z" fill="#fff" />
      </svg>
      <span>YouTube Clone</span>
    </RouterLink>

    <form class="search" role="search" @submit.prevent="onSearch">
      <input v-model="query" type="search" maxlength="100" placeholder="Введите запрос" aria-label="Поиск" />
      <button class="btn" aria-label="Найти">Найти</button>
    </form>

    <div class="right">
      <template v-if="state.ready">
        <RouterLink v-if="state.user" to="/upload" class="btn upload-btn">Загрузить</RouterLink>
        <div v-if="state.user" class="user">
          <button class="avatar" type="button" @click="menuOpen = !menuOpen">
            {{ initial }}
          </button>
          <div v-if="menuOpen" class="backdrop" @click="menuOpen = false" />
          <div v-if="menuOpen" class="menu">
            <div class="menu-head">
              <div class="menu-name">{{ state.user.channel.name }}</div>
              <div class="menu-handle">@{{ state.user.channel.handle }}</div>
              <div v-if="roleLabel" class="menu-role">{{ roleLabel }}</div>
              <RouterLink class="menu-item" :to="`/@${state.user.channel.handle}`" @click="menuOpen = false">Мой канал</RouterLink>
              <RouterLink class="menu-item" to="/studio" @click="menuOpen = false">Мои видео</RouterLink>
              <RouterLink v-if="isModerator" class="menu-item" to="/moderation" @click="menuOpen = false">Модерация</RouterLink>
              <RouterLink v-if="isAdmin" class="menu-item" to="/admin" @click="menuOpen = false">Администрирование</RouterLink>
            </div>
            <button class="menu-item" type="button" @click="onLogout">Выйти</button>
          </div>
        </div>
        <RouterLink v-else to="/login" class="btn btn-primary">Войти</RouterLink>
      </template>
    </div>
  </header>
</template>

<style scoped>
.header {
  position: fixed;
  inset: 0 0 auto 0;
  z-index: 100;
  display: flex;
  align-items: center;
  justify-content: space-between;
  height: var(--header-height);
  padding: 0 16px;
  background: var(--bg);
}
.logo {
  display: flex;
  align-items: center;
  gap: 6px;
  color: var(--text);
  font-size: 18px;
  font-weight: 700;
  letter-spacing: -0.5px;
}
.right {
  display: flex;
  align-items: center;
}
.user {
  position: relative;
}
.avatar {
  width: 32px;
  height: 32px;
  border: none;
  border-radius: 50%;
  background: var(--link);
  color: #0f0f0f;
  font: inherit;
  font-weight: 500;
  cursor: pointer;
}
.backdrop {
  position: fixed;
  inset: 0;
  z-index: 1;
}
.menu {
  position: absolute;
  right: 0;
  top: 44px;
  z-index: 2;
  min-width: 220px;
  padding: 8px 0;
  background: var(--surface);
  border-radius: var(--radius);
  box-shadow: 0 4px 32px rgba(0, 0, 0, 0.4);
}
.menu-head {
  padding: 8px 16px 12px;
  border-bottom: 1px solid var(--border);
}
.menu-name {
  font-weight: 500;
}
.menu-handle,
.menu-role {
  color: var(--text-secondary);
}
.menu-item {
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
.menu-item:hover {
  background: var(--surface-hover);
}
.upload-btn {
  margin-right: 12px;
}
.search {
  display: flex;
  flex: 1;
  gap: 8px;
  max-width: 600px;
  margin: 0 16px;
}
.search input {
  flex: 1;
  min-width: 0;
  padding: 0 16px;
  height: 36px;
  border: 1px solid var(--border);
  border-radius: 18px;
  background: var(--bg);
  color: var(--text);
  font: inherit;
}
.search input:focus {
  outline: none;
  border-color: var(--link);
}
</style>