<script setup>
import { ref } from 'vue'
import { api } from '../api/client'

const emit = defineEmits(['close', 'deleted'])

const password = ref('')
const busy = ref(false)
const error = ref('')

async function submit() {
  busy.value = true
  error.value = ''
  try {
    await api.account.remove(password.value)
    emit('deleted')
  } catch (e) {
    error.value = e.message
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <Teleport to="body">
    <div class="overlay" @click.self="emit('close')">
      <form class="dialog" role="dialog" aria-modal="true" @submit.prevent="submit">
        <h2>Удалить канал?</h2>
        <p>
          Будут безвозвратно удалены аккаунт, канал, все ваши видео, комментарии, лайки, плейлисты
          и подписки. Отменить это нельзя.
        </p>
        <label class="field">
          <span>Введите пароль для подтверждения</span>
          <input v-model="password" type="password" autocomplete="current-password" required />
        </label>
        <p v-if="error" class="error" role="alert">{{ error }}</p>
        <div class="row">
          <button type="button" class="btn" @click="emit('close')">Отмена</button>
          <button class="btn danger" :disabled="busy || !password">Удалить навсегда</button>
        </div>
      </form>
    </div>
  </Teleport>
</template>

<style scoped>
.overlay {
  position: fixed;
  inset: 0;
  z-index: 200;
  display: grid;
  place-items: center;
  padding: 16px;
  background: rgba(0, 0, 0, 0.6);
}
.dialog {
  width: 100%;
  max-width: 440px;
  padding: 24px;
  border-radius: var(--radius);
  background: var(--surface);
  color: var(--text);
}
h2 {
  margin: 0 0 12px;
  font-size: 18px;
  font-weight: 500;
}
p {
  margin: 0 0 16px;
}
.row {
  display: flex;
  gap: 8px;
  justify-content: flex-end;
}
.danger {
  background: var(--danger);
  color: var(--bg);
}
.danger:hover {
  background: var(--danger);
  filter: brightness(1.1);
}
</style>