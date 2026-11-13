<script setup>
import { onMounted } from 'vue'
import AppHeader from './components/AppHeader.vue'
import { useAuth } from './composables/useAuth'

const { init } = useAuth()
onMounted(init)
</script>

<template>
  <AppHeader />
  <main class="page">
    <RouterView />
  </main>
</template>