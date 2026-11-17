<script setup>
import { ref, watch } from 'vue'
import { api } from '../api/client'
import { useCategories } from '../composables/useCategories'

const props = defineProps({ video: { type: Object, required: true } })
const emit = defineEmits(['saved', 'cancel'])

const title = ref(props.video.title)
const description = ref(props.video.description)
const visibility = ref(props.video.visibility)
const { categories } = useCategories()
const category = ref(props.video.category_id)
const busy = ref(false)
const error = ref('')

async function submit() {
  busy.value = true
  error.value = ''
  try {
    emit(
      'saved',
      await api.videos.update(props.video.id, {
        title: title.value.trim(),
        description: description.value,
        visibility: visibility.value,
        category_id: category.value,
      }),
    )
  } catch (e) {
    error.value = e.message
  } finally {
    busy.value = false
  }
}

// --- кому разрешён приватный доступ (применяется сразу, без кнопки «Сохранить») ---
const shares = ref([])
const sharesLoaded = ref(false)
const sharesError = ref('')
const username = ref('')
const sharing = ref(false)

async function loadShares() {
  sharesLoaded.value = true
  try {
    shares.value = await api.videos.shares.list(props.video.id)
  } catch (e) {
    sharesError.value = e.message
  }
}

watch(
  visibility,
  (v) => {
    if (v === 'private' && !sharesLoaded.value) loadShares()
  },
  { immediate: true },
)

async function addShare() {
  const name = username.value.trim()
  if (!name || sharing.value) return
  sharing.value = true
  sharesError.value = ''
  try {
    const user = await api.videos.shares.add(props.video.id, name)
    if (!shares.value.some((s) => s.id === user.id)) shares.value.push(user)
    username.value = ''
  } catch (e) {
    sharesError.value = e.message
  } finally {
    sharing.value = false
  }
}

async function removeShare(user) {
  sharesError.value = ''
  try {
    await api.videos.shares.remove(props.video.id, user.id)
    shares.value = shares.value.filter((s) => s.id !== user.id)
  } catch (e) {
    sharesError.value = e.message
  }
}
</script>

<template>
  <div class="edit">
    <form @submit.prevent="submit">
      <label class="field">
        <span>Название</span>
        <input v-model="title" maxlength="100" required />
      </label>
      <label class="field">
        <span>Описание</span>
        <textarea v-model="description" maxlength="5000" />
      </label>
      <label class="field">
        <span>Доступ</span>
        <select v-model="visibility">
          <option value="public">Открытый доступ</option>
          <option value="unlisted">Доступ по ссылке</option>
          <option value="private">Ограниченный доступ</option>
        </select>
      </label>
      <label class="field">
        <span>Категория</span>
        <select v-model="category">
          <option v-for="c in categories" :key="c.id" :value="c.id">{{ c.name }}</option>
        </select>
      </label>
      <p v-if="error" class="error" role="alert">{{ error }}</p>
      <div class="row">
        <button type="button" class="btn" @click="emit('cancel')">Отмена</button>
        <button class="btn btn-primary" :disabled="busy || !title.trim()">Сохранить</button>
      </div>
    </form>

    <section v-if="visibility === 'private'" class="shares">
      <h3>Кто может смотреть</h3>
      <p v-if="sharesLoaded && !shares.length" class="muted">Пока никому не выдан доступ</p>
      <ul>
        <li v-for="s in shares" :key="s.id">
          <span>@{{ s.username }}</span>
          <button type="button" class="link" @click="removeShare(s)">Убрать</button>
        </li>
      </ul>
      <form class="row" @submit.prevent="addShare">
        <input v-model="username" maxlength="30" placeholder="Имя пользователя" />
        <button class="btn" :disabled="sharing || !username.trim()">Выдать доступ</button>
      </form>
      <p v-if="sharesError" class="error" role="alert">{{ sharesError }}</p>
    </section>
  </div>
</template>

<style scoped>
.row {
  display: flex;
  gap: 8px;
}
.shares {
  margin-top: 20px;
  padding-top: 16px;
  border-top: 1px solid var(--border);
}
h3 {
  margin: 0 0 8px;
  font-size: 16px;
  font-weight: 500;
}
ul {
  margin: 0 0 12px;
  padding: 0;
  list-style: none;
}
li {
  display: flex;
  gap: 16px;
  align-items: center;
  padding: 4px 0;
}
.shares input {
  flex: 1;
  min-width: 0;
  padding: 6px 10px;
  border: 1px solid var(--border);
  border-radius: 8px;
  background: var(--bg);
  color: var(--text);
  font: inherit;
}
</style>