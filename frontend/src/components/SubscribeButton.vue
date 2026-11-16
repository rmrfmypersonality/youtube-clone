<script setup>
import { ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { api } from '../api/client'
import { useAuth } from '../composables/useAuth'
import { useSubscriptions } from '../composables/useSubscriptions'

const props = defineProps({
  handle: { type: String, required: true },
  subscribed: Boolean,
})
const emit = defineEmits(['changed'])

const route = useRoute()
const router = useRouter()
const { state: auth } = useAuth()
const { reload: reloadSubscriptions } = useSubscriptions()
const busy = ref(false)
const error = ref('')

async function toggle() {
  if (!auth.user) {
    router.push({ name: 'login', query: { next: route.fullPath } })
    return
  }
  if (busy.value) return
  busy.value = true
  error.value = ''
  try {
    const res = props.subscribed
      ? await api.channels.unsubscribe(props.handle)
      : await api.channels.subscribe(props.handle)
    emit('changed', res)
    reloadSubscriptions()
  } catch (e) {
    error.value = e.message
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <span class="wrap">
    <button type="button" class="sub" :class="{ on: subscribed }" :disabled="busy" @click="toggle">
      {{ subscribed ? 'Вы подписаны' : 'Подписаться' }}
    </button>
    <span v-if="error" class="error" role="alert">{{ error }}</span>
  </span>
</template>

<style scoped>
.sub {
  height: 36px;
  padding: 0 16px;
  border: none;
  border-radius: 18px;
  background: var(--accent);
  color: #fff;
  font: inherit;
  font-weight: 500;
  cursor: pointer;
  transition: filter 0.15s;
}
.sub:hover {
  filter: brightness(1.1);
}
.sub.on {
  background: var(--surface);
  color: var(--text);
}
.sub:disabled {
  opacity: 0.6;
  cursor: default;
}
</style>