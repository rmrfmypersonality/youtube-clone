<script setup>
import { computed, nextTick, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import AppIcon from './AppIcon.vue'
import AppLogo from './AppLogo.vue'
import { useAuth } from '../composables/useAuth'
import { useLayout } from '../composables/useLayout'
import { useTheme } from '../composables/useTheme'

const { state, logout, isModerator, isAdmin } = useAuth()
const { toggleSidebar } = useLayout()
const { theme, toggleTheme } = useTheme()
const router = useRouter()
const route = useRoute()

const ROLE_LABELS = { moderator: 'Модератор', admin: 'Администратор' }

const menuOpen = ref(false)
const query = ref(String(route.query.q ?? ''))
const mobileSearch = ref(false) // на телефоне поиск раскрывается поверх шапки
const searchInput = ref(null)

const initial = computed(() => state.user?.username?.[0]?.toUpperCase() ?? '')
const roleLabel = computed(() => ROLE_LABELS[state.user?.role] ?? null)

watch(
  () => route.query.q,
  (value) => {
    query.value = String(value ?? '')
  },
)
watch(
  () => route.fullPath,
  () => {
    menuOpen.value = false
  },
)

function onSearch() {
  const q = query.value.trim()
  if (!q) return
  mobileSearch.value = false
  router.push({ name: 'search', query: { q } })
}

async function openMobileSearch() {
  mobileSearch.value = true
  await nextTick()
  searchInput.value?.focus()
}

async function onLogout() {
  menuOpen.value = false
  await logout()
  router.push('/')
}
</script>

<template>
  <header class="header" :class="{ 'search-open': mobileSearch }">
    <div class="left">
      <button type="button" class="icon-btn" aria-label="Меню" @click="toggleSidebar">
        <AppIcon name="menu" />
      </button>
      <AppLogo />
    </div>

    <form class="search" role="search" @submit.prevent="onSearch">
      <button type="button" class="icon-btn back" aria-label="Назад" @click="mobileSearch = false">
        <AppIcon name="back" />
      </button>
      <div class="field-wrap">
        <input
          ref="searchInput"
          v-model="query"
          type="search"
          maxlength="100"
          placeholder="Введите запрос"
          aria-label="Поиск"
        />
        <button class="submit" aria-label="Найти"><AppIcon name="search" /></button>
      </div>
    </form>

    <div class="right">
      <button
        type="button"
        class="icon-btn mobile-only"
        aria-label="Поиск"
        @click="openMobileSearch"
      >
        <AppIcon name="search" />
      </button>
      <button
        type="button"
        class="icon-btn"
        :aria-label="theme === 'dark' ? 'Включить светлую тему' : 'Включить тёмную тему'"
        @click="toggleTheme"
      >
        <AppIcon :name="theme === 'dark' ? 'sun' : 'moon'" />
      </button>

      <template v-if="state.ready">
        <RouterLink v-if="state.user" to="/upload" class="pill create">
          <AppIcon name="add" />
          <span>Создать</span>
        </RouterLink>

        <div v-if="state.user" class="user">
          <button class="avatar" type="button" aria-label="Аккаунт" @click="menuOpen = !menuOpen">
            {{ initial }}
          </button>
          <div v-if="menuOpen" class="backdrop" @click="menuOpen = false" />
          <div v-if="menuOpen" class="menu">
            <div class="menu-head">
              <div class="menu-name">{{ state.user.channel.name }}</div>
              <div class="muted">@{{ state.user.channel.handle }}</div>
              <div v-if="roleLabel" class="muted">{{ roleLabel }}</div>
            </div>
            <RouterLink class="menu-item" :to="`/@${state.user.channel.handle}`">
              Мой канал
            </RouterLink>
            <RouterLink class="menu-item" to="/studio">Мои видео</RouterLink>
            <RouterLink class="menu-item" to="/settings">Настройки</RouterLink>
            <RouterLink v-if="isModerator" class="menu-item" to="/moderation">Модерация</RouterLink>
            <RouterLink v-if="isAdmin" class="menu-item" to="/admin">Администрирование</RouterLink>
            <button class="menu-item" type="button" @click="onLogout">Выйти</button>
          </div>
        </div>

        <RouterLink v-else to="/login" class="pill signin">
          <AppIcon name="account" />
          <span>Войти</span>
        </RouterLink>
      </template>
    </div>
  </header>
</template>

<style scoped>
.header {
  position: fixed;
  inset: 0 0 auto 0;
  z-index: 100;
  display: grid;
  grid-template-columns: 1fr minmax(0, 720px) 1fr;
  align-items: center;
  height: var(--header-height);
  padding: 0 16px;
  background: var(--bg);
}
.left {
  grid-column: 1;
  display: flex;
  align-items: center;
  gap: 8px;
  justify-self: start;
}
.search {
  grid-column: 2;
  display: flex;
  align-items: center;
  min-width: 0;
}
.right {
  grid-column: 3;
  display: flex;
  align-items: center;
  gap: 8px;
  justify-self: end;
}
.field-wrap {
  display: flex;
  flex: 1;
  min-width: 0;
}
.search input {
  flex: 1;
  min-width: 0;
  height: 40px;
  padding: 0 16px;
  border: 1px solid var(--border);
  border-radius: 20px 0 0 20px;
  background: var(--bg);
  color: var(--text);
  font: inherit;
  font-size: 16px;
}
.search input:focus {
  outline: none;
  border-color: var(--link);
}
.submit {
  display: grid;
  place-items: center;
  width: 64px;
  height: 40px;
  padding: 0;
  border: 1px solid var(--border);
  border-left: none;
  border-radius: 0 20px 20px 0;
  background: var(--surface);
  color: var(--text);
  cursor: pointer;
}
.submit:hover {
  background: var(--surface-hover);
}
.back,
.mobile-only {
  display: none;
}
.signin {
  border: 1px solid var(--border);
  background: transparent;
  color: var(--link);
}
.signin:hover {
  background: var(--surface);
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
  color: var(--on-link);
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
  min-width: 240px;
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

@media (max-width: 1024px) {
  .header {
    grid-template-columns: auto minmax(0, 1fr) auto;
  }
  .search {
    margin: 0 16px;
  }
}

@media (max-width: 640px) {
  .header {
    padding: 0 8px;
  }
  .search {
    display: none;
  }
  .mobile-only {
    display: grid;
  }
  .create span {
    display: none;
  }
  .create {
    width: 36px;
    padding: 0;
    justify-content: center;
  }
  .signin span {
    display: none;
  }
  .signin {
    width: 36px;
    padding: 0;
    justify-content: center;
  }
  .header.search-open .left,
  .header.search-open .right {
    display: none;
  }
  .header.search-open .search {
    display: flex;
    grid-column: 1 / -1;
    margin: 0;
  }
  .header.search-open .back {
    display: grid;
  }
}
</style>