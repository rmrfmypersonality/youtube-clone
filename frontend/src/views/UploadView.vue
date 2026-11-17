<script setup>
import { computed, ref, watch } from 'vue'
import { useVideoUpload } from '../composables/useVideoUpload'
import { formatSize } from '../composables/format'
import { useCategories } from '../composables/useCategories'

const MAX_MB = 500 // держать в синхроне с MAX_UPLOAD_MB на бэкенде
const ACCEPT = '.mp4,.mov,.webm,.mkv,video/mp4,video/quicktime,video/webm,video/x-matroska'

const upload = useVideoUpload()
const fileInput = ref(null)
const file = ref(null)
const fileError = ref('')
const dragging = ref(false)
const title = ref('')
const description = ref('')
const visibility = ref('public')
const { categories, defaultId } = useCategories()
const category = ref(null)

// Когда справочник загрузился, выбираем «Другое»
watch(
  categories,
  () => {
    if (category.value === null) category.value = defaultId()
  },
  { immediate: true },
)

const showForm = computed(() => ['idle', 'error'].includes(upload.state.phase))
const lockMeta = computed(() => !!upload.state.video) // запись уже создана, метаданные не меняем
const canSubmit = computed(() => file.value && title.value.trim())
const percent = computed(() => Math.round(upload.state.progress * 100))

const PROCESSING_TEXT = {
  uploaded: 'В очереди на обработку…',
  processing: 'Обрабатываем: кодируем 720p и 360p, делаем превью…',
}

function pick(f) {
  fileError.value = ''
  if (!f) return
  if (f.size > MAX_MB * 1024 * 1024) {
    fileError.value = `Файл больше ${MAX_MB} МБ`
    return
  }
  if (!/\.(mp4|mov|webm|mkv)$/i.test(f.name)) {
    fileError.value = 'Поддерживаются MP4, MOV, WebM и MKV'
    return
  }
  file.value = f
  if (!title.value) title.value = f.name.replace(/\.[^.]+$/, '').slice(0, 100)
}

function onPick(e) {
  pick(e.target.files[0])
  e.target.value = ''
}

function onDrop(e) {
  dragging.value = false
  pick(e.dataTransfer.files[0])
}

function submit() {
  upload.start(file.value, {
    title: title.value.trim(),
    description: description.value,
    visibility: visibility.value,
    category_id: category.value,
  })
}

function again() {
  upload.reset()
  file.value = null
  title.value = ''
  description.value = ''
  visibility.value = 'public'
  category.value = defaultId()
}
</script>

<template>
  <div class="upload">
    <h1>Загрузка видео</h1>

    <form v-if="showForm" @submit.prevent="submit">
      <div
        class="drop"
        :class="{ over: dragging, filled: file }"
        role="button"
        tabindex="0"
        @click="fileInput.click()"
        @keydown.enter="fileInput.click()"
        @dragover.prevent="dragging = true"
        @dragleave.prevent="dragging = false"
        @drop.prevent="onDrop"
      >
        <input ref="fileInput" type="file" :accept="ACCEPT" hidden @change="onPick" />
        <template v-if="file">
          <strong>{{ file.name }}</strong>
          <span>{{ formatSize(file.size) }}</span>
        </template>
        <template v-else>
          <strong>Перетащите видео сюда</strong>
          <span>или нажмите, чтобы выбрать файл (MP4, MOV, WebM, MKV, до {{ MAX_MB }} МБ)</span>
        </template>
      </div>
      <p v-if="fileError" class="error" role="alert">{{ fileError }}</p>

      <label class="field">
        <span>Название</span>
        <input v-model="title" maxlength="100" required :disabled="lockMeta" />
      </label>
      <label class="field">
        <span>Описание</span>
        <textarea v-model="description" maxlength="5000" :disabled="lockMeta" />
      </label>
      <label class="field">
        <span>Доступ</span>
        <select v-model="visibility" :disabled="lockMeta">
          <option value="public">Открытый доступ</option>
          <option value="unlisted">Доступ по ссылке</option>
          <option value="private">Ограниченный доступ</option>
        </select>
      </label>
      <label class="field">
        <span>Категория</span>
        <select v-model="category" :disabled="lockMeta">
          <option v-for="c in categories" :key="c.id" :value="c.id">{{ c.name }}</option>
        </select>
      </label>

      <p v-if="upload.state.error" class="error" role="alert">{{ upload.state.error }}</p>
      <button class="btn btn-primary" :disabled="!canSubmit">
        {{ upload.state.video ? 'Повторить загрузку' : 'Загрузить' }}
      </button>
    </form>

    <section v-else class="status">
      <h2>{{ upload.state.video?.title }}</h2>

      <template v-if="upload.state.phase === 'uploading'">
        <div class="bar"><div class="bar-fill" :style="{ width: percent + '%' }" /></div>
        <p>Загружаем файл: {{ percent }}%</p>
        <p class="hint">Не закрывайте страницу, пока идёт загрузка файла.</p>
        <button class="btn" type="button" @click="upload.cancel()">Отменить</button>
      </template>

      <template v-else-if="upload.state.phase === 'processing'">
        <div class="bar"><div class="bar-fill indeterminate" /></div>
        <p>{{ PROCESSING_TEXT[upload.state.video.status] ?? 'Обрабатываем…' }}</p>
        <p class="hint">Страницу можно закрыть, обработка продолжится на сервере.</p>
      </template>

      <template v-else-if="upload.state.phase === 'ready'">
        <p>Видео обработано и готово.</p>
        <div class="actions">
          <RouterLink :to="`/watch/${upload.state.video.id}`" class="btn btn-primary">
            Смотреть
          </RouterLink>
          <button class="btn" type="button" @click="again">Загрузить ещё</button>
        </div>
      </template>

      <template v-else-if="upload.state.phase === 'failed'">
        <p class="error">
          Не удалось обработать видео. Проверьте, что файл является корректным видео, и попробуйте другой.
        </p>
        <button class="btn" type="button" @click="again">Загрузить другой файл</button>
      </template>
    </section>
  </div>
</template>

<style scoped>
.upload {
  max-width: 720px;
  margin: 0 auto;
  padding: 24px 16px;
}
h1 {
  margin: 0 0 24px;
  font-size: 22px;
  font-weight: 500;
}
h2 {
  margin: 0 0 16px;
  font-size: 18px;
  font-weight: 500;
  overflow-wrap: anywhere;
}
.drop {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
  margin-bottom: 20px;
  padding: 40px 16px;
  border: 2px dashed var(--border);
  border-radius: var(--radius);
  background: var(--surface);
  color: var(--text-secondary);
  text-align: center;
  cursor: pointer;
  transition: border-color 0.15s, background 0.15s;
}
.drop strong {
  color: var(--text);
  font-weight: 500;
  overflow-wrap: anywhere;
}
.drop:hover,
.drop.over {
  border-color: var(--link);
  background: var(--surface-hover);
}
.status {
  padding: 24px;
  background: var(--surface);
  border-radius: var(--radius);
}
.bar {
  height: 8px;
  margin-bottom: 12px;
  overflow: hidden;
  background: var(--bg);
  border-radius: 4px;
}
.bar-fill {
  height: 100%;
  background: var(--link);
  transition: width 0.2s;
}
.bar-fill.indeterminate {
  width: 30%;
  animation: slide 1.2s ease-in-out infinite;
}
@keyframes slide {
  0% { margin-left: -30%; }
  100% { margin-left: 100%; }
}
.hint {
  color: var(--text-secondary);
}
.actions {
  display: flex;
  gap: 8px;
}
</style>