<script setup>
import { ref } from 'vue'
import { api } from '../api/client'
import { REPORT_REASONS } from '../composables/moderation'

const props = defineProps({
  kind: { type: String, required: true }, // 'video' | 'comment'
  targetId: { type: Number, required: true },
})
const emit = defineEmits(['close'])

const reason = ref('spam')
const details = ref('')
const busy = ref(false)
const error = ref('')
const sent = ref(false)

async function submit() {
  busy.value = true
  error.value = ''
  try {
    const payload = { reason: reason.value, details: details.value.trim() }
    if (props.kind === 'video') await api.reports.video(props.targetId, payload)
    else await api.reports.comment(props.targetId, payload)
    sent.value = true
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
      <div class="dialog" role="dialog" aria-modal="true">
        <template v-if="sent">
          <h2>Спасибо</h2>
          <p>Жалоба отправлена, модераторы её рассмотрят.</p>
          <div class="row">
            <button type="button" class="btn btn-primary" @click="emit('close')">Закрыть</button>
          </div>
        </template>

        <form v-else @submit.prevent="submit">
          <h2>{{ kind === 'video' ? 'Пожаловаться на видео' : 'Пожаловаться на комментарий' }}</h2>
          <label class="field">
            <span>Причина</span>
            <select v-model="reason">
              <option v-for="(label, value) in REPORT_REASONS" :key="value" :value="value">
                {{ label }}
              </option>
            </select>
          </label>
          <label class="field">
            <span>Подробности (необязательно)</span>
            <textarea v-model="details" maxlength="1000" />
          </label>
          <p v-if="error" class="error" role="alert">{{ error }}</p>
          <div class="row">
            <button type="button" class="btn" @click="emit('close')">Отмена</button>
            <button class="btn btn-primary" :disabled="busy">Отправить</button>
          </div>
        </form>
      </div>
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
  margin: 0 0 16px;
  font-size: 18px;
  font-weight: 500;
}
.row {
  display: flex;
  gap: 8px;
  justify-content: flex-end;
}
</style>