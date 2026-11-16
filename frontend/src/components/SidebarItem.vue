<script setup>
import AppIcon from './AppIcon.vue'

defineProps({
  to: { type: String, required: true },
  label: { type: String, required: true },
  icon: { type: String, default: '' },
  mini: Boolean,
})
</script>

<template>
  <RouterLink :to="to" class="item" :class="{ mini }" active-class="" exact-active-class="active">
    <span class="ico">
      <slot name="icon"><AppIcon v-if="icon" :name="icon" /></slot>
    </span>
    <span class="label">{{ label }}</span>
  </RouterLink>
</template>

<style scoped>
.item {
  display: flex;
  align-items: center;
  gap: 24px;
  height: 40px;
  padding: 0 12px;
  border-radius: 10px;
  color: var(--text);
  font-size: 14px;
}
.item:hover {
  background: var(--surface);
}
.item.active {
  background: var(--surface);
  font-weight: 500;
}
.ico {
  display: grid;
  flex: none;
  place-items: center;
  width: 24px;
  height: 24px;
}
.label {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.item.mini {
  flex-direction: column;
  justify-content: center;
  gap: 6px;
  height: auto;
  padding: 16px 0 14px;
  font-size: 10px;
}
.item.mini .label {
  max-width: 100%;
}
</style>