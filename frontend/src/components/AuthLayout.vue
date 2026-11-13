<script setup>
defineProps({ title: { type: String, required: true } })
</script>

<template>
  <div class="auth-card">
    <h1>{{ title }}</h1>
    <slot />
    <p class="footer"><slot name="footer" /></p>
  </div>
</template>

<style scoped>
.auth-card {
  max-width: 400px;
  margin: 48px auto;
  padding: 32px;
  background: var(--surface);
  border-radius: var(--radius);
}
h1 {
  margin: 0 0 24px;
  font-size: 24px;
  font-weight: 500;
}
.auth-card :deep(.btn) {
  width: 100%;
}
.footer {
  margin: 20px 0 0;
  color: var(--text-secondary);
  text-align: center;
}
</style>