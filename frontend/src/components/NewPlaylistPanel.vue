<script setup>
import { ref } from 'vue'
import { api } from '../api/client'
import { VISIBILITY_LABELS } from '../composables/visibility'

const emit = defineEmits(['created', 'cancel'])

const title = ref('')
const visibility = ref('private')
const busy = ref(false)
const error = ref('')

async function submit() {
  const value = title.value.trim()
  if (!value || busy.value) return
  busy.value = true
  error.value = ''
  try {
    emit('created', await api.playlists.create({ title: value, visibility: visibility.value }))
  } catch (e) {
    error.value = e.message
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <form @submit.prevent="submit">
    <h2>Новый</h2>
    <input
      v-model="title"
      class="title"
      maxlength="100"
      placeholder="Укажите название"
      aria-label="Название плейлиста"
      autofocus
    />
    <label class="access">
      <span>Доступ</span>
      <select v-model="visibility">
        <option v-for="(label, value) in VISIBILITY_LABELS" :key="value" :value="value">
          {{ label }}
        </option>
      </select>
    </label>
    <p v-if="error" class="error" role="alert">{{ error }}</p>
    <div class="row">
      <button type="button" class="pill" @click="emit('cancel')">Отмена</button>
      <button class="pill primary" :disabled="busy || !title.trim()">Создать</button>
    </div>
  </form>
</template>

<style scoped>
h2 {
  margin: 0 0 16px;
  font-size: 20px;
  font-weight: 500;
}
.title {
  width: 100%;
  height: 56px;
  padding: 0 14px;
  border: 1px solid var(--border);
  border-radius: 8px;
  background: transparent;
  color: var(--text);
  font: inherit;
  font-size: 16px;
}
.title:focus {
  outline: none;
  border-color: var(--link);
}
.access {
  display: block;
  margin-top: 12px;
  padding: 6px 10px;
  border: 1px solid var(--border);
  border-radius: 8px;
}
.access span {
  display: block;
  color: var(--text-secondary);
  font-size: 12px;
}
.access select {
  width: 100%;
  padding: 2px 0;
  border: none;
  background: transparent;
  color: var(--text);
  font: inherit;
  font-size: 16px;
}
.access select option {
  background: var(--surface);
}
.row {
  display: flex;
  gap: 8px;
  justify-content: flex-end;
  margin-top: 20px;
}
.primary {
  background: var(--text);
  color: var(--bg);
}
.primary:disabled {
  background: var(--surface-hover);
  color: var(--text-secondary);
}
</style>