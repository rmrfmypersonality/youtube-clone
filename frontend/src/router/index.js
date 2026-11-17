import { createRouter, createWebHistory } from 'vue-router'
import { useAuth } from '../composables/useAuth'
import ChannelView from '../views/ChannelView.vue'
import HomeView from '../views/HomeView.vue'
import LoginView from '../views/LoginView.vue'
import PlaylistView from '../views/PlaylistView.vue'
import RegisterView from '../views/RegisterView.vue'
import SearchView from '../views/SearchView.vue'
import StudioView from '../views/StudioView.vue'
import UploadView from '../views/UploadView.vue'
import WatchView from '../views/WatchView.vue'
import AdminView from '../views/AdminView.vue'
import ModerationView from '../views/ModerationView.vue'
import SubscriptionsView from '../views/SubscriptionsView.vue'
import SettingsView from '../views/SettingsView.vue'
import HistoryView from '../views/HistoryView.vue'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', name: 'home', component: HomeView },
    { path: '/login', name: 'login', component: LoginView },
    { path: '/register', name: 'register', component: RegisterView },
    { path: '/upload', name: 'upload', component: UploadView, meta: { requiresAuth: true } },
    { path: '/studio', name: 'studio', component: StudioView, meta: { requiresAuth: true } },
    { path: '/watch/:id(\\d+)', name: 'watch', component: WatchView },
    { path: '/search', name: 'search', component: SearchView },
    { path: '/playlist/:id(\\d+)', name: 'playlist', component: PlaylistView },
    { path: '/@:handle/:tab(videos|playlists)?', name: 'channel', component: ChannelView },
    { path: '/moderation', name: 'moderation', component: ModerationView, meta: { requiresAuth: true, role: 'moderator' },},
    { path: '/admin', name: 'admin', component: AdminView, meta: { requiresAuth: true, role: 'admin' },},
    { path: '/subscriptions', name: 'subscriptions', component: SubscriptionsView, meta: { requiresAuth: true },},
    { path: '/settings', name: 'settings', component: SettingsView, meta: { requiresAuth: true } },
    { path: '/watch-later', name: 'watch-later', component: PlaylistView, meta: { requiresAuth: true },},
    { path: '/history', name: 'history', component: HistoryView, meta: { requiresAuth: true } },
  ],
})

router.beforeEach(async (to) => {
  if (!to.meta.requiresAuth) return true
  const { state, init } = useAuth()
  await init() // ждём, пока выяснится, залогинен ли пользователь
  if (!state.user) return { name: 'login', query: { next: to.fullPath } }
  const role = state.user.role
  if (to.meta.role === 'admin' && role !== 'admin') return { name: 'home' }
  if (to.meta.role === 'moderator' && !['moderator', 'admin'].includes(role)) {
    return { name: 'home' }
  }
  return true
})

export default router