<script setup>
import { onMounted, watch } from 'vue'
import { useRoute } from 'vue-router'
import AppHeader from './components/AppHeader.vue'
import AppSidebar from './components/AppSidebar.vue'
import { useAuth } from './composables/useAuth'
import { useLayout } from './composables/useLayout'

const route = useRoute()
const { init } = useAuth()
const { layoutClass, setWatchPage, closeDrawer } = useLayout()

onMounted(init)

// На странице просмотра сайдбар скрыт и выезжает поверх контента
watch(() => route.name, (name) => setWatchPage(name === 'watch'), { immediate: true })
watch(() => route.fullPath, closeDrawer)
</script>

<template>
  <AppHeader />
  <AppSidebar />
  <main class="page" :class="layoutClass">
    <RouterView />
  </main>
</template>