<script setup>
import { useRouter } from 'vue-router'

// Категорий в БД нет: чипсы это быстрый поиск по слову
const TOPICS = ['Музыка', 'Игры', 'Новости', 'Кино', 'Спорт', 'Обучение', 'Наука', 'Путешествия']

const router = useRouter()

function open(topic) {
  router.push({ name: 'search', query: { q: topic } })
}
</script>

<template>
  <div class="chips" role="toolbar" aria-label="Категории">
    <button type="button" class="pill sm active">Все</button>
    <button v-for="t in TOPICS" :key="t" type="button" class="pill sm" @click="open(t)">
      {{ t }}
    </button>
  </div>
</template>

<style scoped>
.chips {
  position: sticky;
  top: var(--header-height);
  z-index: 50;
  display: flex;
  gap: 12px;
  padding: 12px 24px;
  overflow-x: auto;
  background: var(--bg);
  scrollbar-width: none;
}
.chips::-webkit-scrollbar {
  display: none;
}
.chips .pill {
  height: 32px;
}
@media (max-width: 600px) {
  .chips {
    padding: 8px 12px;
  }
}
</style>