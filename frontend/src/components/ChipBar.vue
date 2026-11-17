<script setup>
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useCategories } from '../composables/useCategories'

const route = useRoute()
const router = useRouter()
const { categories } = useCategories()

const active = computed(() => String(route.query.category ?? ''))

function select(slug) {
  router.push({ name: 'home', query: slug ? { category: slug } : {} })
}
</script>

<template>
  <div class="chips" role="toolbar" aria-label="Категории">
    <button type="button" class="pill sm" :class="{ active: !active }" @click="select('')">
      Все
    </button>
    <button
      v-for="c in categories"
      :key="c.id"
      type="button"
      class="pill sm"
      :class="{ active: active === c.slug }"
      @click="select(c.slug)"
    >
      {{ c.name }}
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