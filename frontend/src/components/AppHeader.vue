<script setup>
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuth } from '../composables/useAuth'

const { state, logout } = useAuth()
const router = useRouter()
const menuOpen = ref(false)

const ROLE_LABELS = { moderator: 'Модератор', admin: 'Администратор' }

const initial = computed(() => state.user?.username?.[0]?.toUpperCase() ?? '')
const roleLabel = computed(() => ROLE_LABELS[state.user?.role] ?? null)

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

    <div class="right">
      <template v-if="state.ready">
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
</style>