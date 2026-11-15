<script setup>
import { ref } from 'vue'
import { api } from '../api/client'

const props = defineProps({ channel: { type: Object, required: true } })
const emit = defineEmits(['saved', 'cancel'])

const name = ref(props.channel.name)
const handle = ref(props.channel.handle)
const description = ref(props.channel.description)
const busy = ref(false)
const error = ref('')

async function submit() {
  busy.value = true
  error.value = ''
  try {
    emit(
      'saved',
      await api.channels.update({
        name: name.value.trim(),
        handle: handle.value.trim(),
        description: description.value,
      }),
    )
  } catch (e) {
    error.value = e.message
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <form class="form" @submit.prevent="submit">
    <label class="field">
      <span>Название канала</span>
      <input v-model="name" maxlength="100" required />
    </label>
    <label class="field">
      <span>Handle (латиница, цифры, _; 3–30 символов)</span>
      <input v-model="handle" required pattern="[A-Za-z0-9_]{3,30}" />
    </label>
    <label class="field">
      <span>Описание</span>
      <textarea v-model="description" maxlength="5000" />
    </label>
    <p v-if="error" class="error" role="alert">{{ error }}</p>
    <div class="row">
      <button type="button" class="btn" @click="emit('cancel')">Отмена</button>
      <button class="btn btn-primary" :disabled="busy || !name.trim()">Сохранить</button>
    </div>
  </form>
</template>

<style scoped>
.form {
  max-width: 520px;
}
.row {
  display: flex;
  gap: 8px;
}
</style>