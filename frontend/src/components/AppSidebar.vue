<script setup>
import { computed, onBeforeUnmount, onMounted } from 'vue'
import AppIcon from './AppIcon.vue'
import AppLogo from './AppLogo.vue'
import SidebarItem from './SidebarItem.vue'
import { useAuth } from '../composables/useAuth'
import { useLayout } from '../composables/useLayout'
import { useSubscriptions } from '../composables/useSubscriptions'

const { state: auth } = useAuth()
const { state: layout, overlay, closeDrawer } = useLayout()
const { state: subs } = useSubscriptions()

// Выезжающий сайдбар всегда полный; постоянный бывает полным и свёрнутым
const full = computed(() => overlay.value || layout.expanded)

const main = [
  { to: '/', label: 'Главная', icon: 'home' },
  { to: '/subscriptions', label: 'Подписки', icon: 'subscriptions' },
]

const mine = computed(() => {
  if (!auth.user) return []
  const handle = auth.user.channel.handle
  return [
    { to: `/@${handle}`, label: 'Мой канал', icon: 'account', fullOnly: true },
    { to: '/history', label: 'История', icon: 'history' },
    { to: `/@${handle}/playlists`, label: 'Плейлисты', icon: 'playlist' },
    { to: '/studio', label: 'Мои видео', icon: 'library' },
    { to: '/settings', label: 'Настройки', icon: 'settings', fullOnly: true },
    { to: '/watch-later', label: 'Смотреть позже', icon: 'watchLater' },
  ]
})

const miniItems = computed(() => [...main, ...mine.value.filter((i) => !i.fullOnly)])

function onKey(e) {
  if (e.key === 'Escape') closeDrawer()
}
onMounted(() => window.addEventListener('keydown', onKey))
onBeforeUnmount(() => window.removeEventListener('keydown', onKey))
</script>

<template>
  <div v-if="overlay && layout.drawer" class="backdrop" @click="closeDrawer" />

  <aside
    class="sidebar"
    :class="{ mini: !full, overlay, open: layout.drawer }"
    :inert="overlay && !layout.drawer"
    aria-label="Навигация"
  >
    <div v-if="overlay" class="drawer-head">
      <button type="button" class="icon-btn" aria-label="Закрыть меню" @click="closeDrawer">
        <AppIcon name="menu" />
      </button>
      <AppLogo />
    </div>

    <nav v-if="full">
      <SidebarItem
        v-for="i in main"
        :key="i.to"
        :to="i.to"
        :label="i.label"
        :icon="i.icon"
      />

      <template v-if="auth.user">
        <div class="sep" />
        <div class="title">Вы</div>
        <SidebarItem
          v-for="i in mine"
          :key="i.to"
          :to="i.to"
          :label="i.label"
          :icon="i.icon"
        />

        <template v-if="subs.channels.length">
          <div class="sep" />
          <div class="title">Подписки</div>
          <SidebarItem
            v-for="c in subs.channels"
            :key="c.id"
            :to="`/@${c.handle}`"
            :label="c.name"
          >
            <template #icon>
              <span class="avatar">{{ c.name[0]?.toUpperCase() }}</span>
            </template>
          </SidebarItem>
        </template>
      </template>

      <div v-else-if="auth.ready" class="signin">
        <p>Войдите, чтобы ставить лайки, комментировать и подписываться на каналы.</p>
        <RouterLink to="/login" class="pill signin-btn">Войти</RouterLink>
      </div>
    </nav>

    <nav v-else>
      <SidebarItem
        v-for="i in miniItems"
        :key="i.to"
        :to="i.to"
        :label="i.label"
        :icon="i.icon"
        mini
      />
    </nav>
  </aside>
</template>

<style scoped>
.sidebar {
  position: fixed;
  top: var(--header-height);
  bottom: 0;
  left: 0;
  z-index: 90;
  width: var(--sidebar-width);
  padding: 12px;
  overflow-y: auto;
  background: var(--bg);
  transition: width 0.2s;
}
.sidebar.mini {
  width: var(--sidebar-mini-width);
  padding: 4px;
}
.sidebar.overlay {
  top: 0;
  z-index: 300;
  padding: 0 12px 12px;
  transform: translateX(-100%);
  transition: transform 0.2s;
}
.sidebar.overlay.open {
  transform: none;
  box-shadow: 0 0 32px rgba(0, 0, 0, 0.5);
}
.backdrop {
  position: fixed;
  inset: 0;
  z-index: 290;
  background: rgba(0, 0, 0, 0.6);
}
.drawer-head {
  display: flex;
  align-items: center;
  gap: 8px;
  height: var(--header-height);
  margin-left: -4px;
}
.sep {
  height: 1px;
  margin: 12px 0;
  background: var(--border);
}
.title {
  padding: 6px 12px;
  font-size: 16px;
  font-weight: 500;
}
.avatar {
  display: grid;
  place-items: center;
  width: 24px;
  height: 24px;
  border-radius: 50%;
  background: var(--link);
  color: var(--on-link);
  font-size: 12px;
  font-weight: 500;
}
.signin {
  margin-top: 12px;
  padding: 12px;
  color: var(--text-secondary);
}
.signin p {
  margin: 0 0 12px;
}
.signin-btn {
  color: var(--link);
}
</style>