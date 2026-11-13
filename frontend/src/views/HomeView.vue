<script setup>
import { ref, onMounted } from 'vue'
import { api } from '../api/client'

const status = ref('проверяю...')

onMounted(async () => {
  try {
    status.value = (await api.health()).status
  } catch (e) {
    status.value = 'ошибка: ' + e.message
  }
})
</script>

<template>
  <div>API: {{ status }}</div>
</template>