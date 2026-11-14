import { createRouter, createWebHistory } from 'vue-router'
import { useAuth } from '../composables/useAuth'
import HomeView from '../views/HomeView.vue'
import LoginView from '../views/LoginView.vue'
import RegisterView from '../views/RegisterView.vue'
import UploadView from '../views/UploadView.vue'
import WatchView from '../views/WatchView.vue'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', name: 'home', component: HomeView },
    { path: '/login', name: 'login', component: LoginView },
    { path: '/register', name: 'register', component: RegisterView },
    { path: '/upload', name: 'upload', component: UploadView, meta: { requiresAuth: true } },
    { path: '/watch/:id(\\d+)', name: 'watch', component: WatchView },
  ],
})

router.beforeEach(async (to) => {
  if (!to.meta.requiresAuth) return true
  const { state, init } = useAuth()
  await init() // ждём, пока выяснится, залогинен ли пользователь
  if (!state.user) return { name: 'login', query: { next: to.fullPath } }
  return true
})

export default router