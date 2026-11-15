<script setup>
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'

const props = defineProps({
  loading: Boolean,
  done: Boolean,
  error: { type: String, default: '' },
})
const emit = defineEmits(['load'])

const el = ref(null)
let observer = null

function observe() {
  if (!observer || !el.value) return
  observer.disconnect()
  if (!props.done) observer.observe(el.value)
}

onMounted(() => {
  observer = new IntersectionObserver(
    (entries) => {
      const visible = entries.some((e) => e.isIntersecting)
      if (visible && !props.loading && !props.done && !props.error) emit('load')
    },
    { rootMargin: '400px' },
  )
  observe()
})

// Любая смена состояния перезапускает наблюдение: observe() сразу выдаёт текущее состояние,
// поэтому если контента мало и сентинель всё ещё виден, подгрузка продолжится сама
watch(() => [props.loading, props.done, props.error], observe)
onBeforeUnmount(() => observer?.disconnect())
</script>

<template>
  <div ref="el" class="sentinel">
    <p v-if="loading" class="muted">Загрузка…</p>
    <p v-else-if="error" class="error" role="alert">
      {{ error }}
      <button type="button" class="btn" @click="emit('load')">Повторить</button>
    </p>
  </div>
</template>

<style scoped>
.sentinel {
  min-height: 1px;
  padding: 16px 0;
  text-align: center;
}
</style>