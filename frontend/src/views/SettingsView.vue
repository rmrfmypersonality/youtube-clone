<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { api } from '../api/client'
import DeleteAccountDialog from '../components/DeleteAccountDialog.vue'
import { useAuth } from '../composables/useAuth'

const router = useRouter()
const { state: auth, setChannel, forget } = useAuth()

const channel = ref(null)
const loading = ref(true)
const loadError = ref('')

const name = ref('')
const handle = ref('')
const saving = ref(false)
const saveError = ref('')
const saved = ref(false)

const hideBusy = ref(false)
const hideError = ref('')
const deleteOpen = ref(false)
const origin = location.origin

const dirty = computed(
  () =>
    !!channel.value &&
    (name.value.trim() !== channel.value.name || handle.value.trim() !== channel.value.handle),
)

function fill(data) {
  channel.value = data
  name.value = data.name
  handle.value = data.handle
}

onMounted(async () => {
  document.title = 'Настройки — YouTube Clone'
  try {
    fill(await api.channels.get(auth.user.channel.handle)) // маршрут requiresAuth: user уже есть
  } catch (e) {
    loadError.value = e.message
  } finally {
    loading.value = false
  }
})

async function save() {
  saving.value = true
  saveError.value = ''
  saved.value = false
  try {
    const updated = await api.channels.update({ name: name.value.trim(), handle: handle.value.trim() })
    fill(updated)
    setChannel({ id: updated.id, handle: updated.handle, name: updated.name })
    saved.value = true
  } catch (e) {
    saveError.value = e.message
  } finally {
    saving.value = false
  }
}

async function toggleHidden() {
  const next = !channel.value.is_hidden
  if (next && !confirm('Скрыть канал? Его страница и все ваши видео станут недоступны другим пользователям.')) {
    return
  }
  hideBusy.value = true
  hideError.value = ''
  try {
    channel.value = { ...channel.value, ...(await api.channels.update({ is_hidden: next })) }
  } catch (e) {
    hideError.value = e.message
  } finally {
    hideBusy.value = false
  }
}

function onDeleted() {
  forget()
  router.push('/')
}
</script>

<template>
  <div class="settings">
    <h1>Настройки канала</h1>
    <p v-if="loading" class="muted">Загрузка…</p>
    <p v-else-if="loadError" class="error" role="alert">{{ loadError }}</p>

    <template v-else-if="channel">
      <form @submit.prevent="save">
        <div class="row">
          <label class="label" for="s-name">Название канала</label>
          <div class="value">
            <input id="s-name" v-model="name" maxlength="100" required />
          </div>
        </div>
        <div class="row">
          <label class="label" for="s-handle">Handle канала</label>
          <div class="value">
            <input
              id="s-handle"
              v-model="handle"
              required
              pattern="[A-Za-z0-9_]{3,30}"
              title="3–30 символов: латинские буквы, цифры, _"
            />
            <div class="muted hint">{{ origin }}/@{{ handle }}</div>
          </div>
        </div>
        <div class="row">
          <div class="label" />
          <div class="value">
            <p v-if="saveError" class="error" role="alert">{{ saveError }}</p>
            <p v-if="saved && !dirty" class="muted" role="status">Сохранено</p>
            <button class="btn btn-primary" :disabled="saving || !dirty || !name.trim()">
              Сохранить
            </button>
          </div>
        </div>
      </form>

      <div class="row">
        <div class="label">{{ channel.is_hidden ? 'Канал скрыт' : 'Скрыть канал' }}</div>
        <div class="value">
          <button type="button" class="act" :disabled="hideBusy" @click="toggleHidden">
            {{ channel.is_hidden ? 'Показать канал' : 'Скрыть канал' }}
          </button>
          <div class="muted">
            {{
              channel.is_hidden
                ? 'Сейчас никто, кроме вас, не может найти канал и посмотреть ваши видео.'
                : 'Никто не сможет найти ваш канал и посмотреть ваши видео.'
            }}
          </div>
          <p v-if="hideError" class="error" role="alert">{{ hideError }}</p>
        </div>
      </div>

      <div class="row">
        <div class="label">Удалить канал</div>
        <div class="value">
          <button type="button" class="act" @click="deleteOpen = true">Удалить канал</button>
          <div class="muted">
            Аккаунт, видео, комментарии и плейлисты будут удалены безвозвратно.
          </div>
        </div>
      </div>

      <DeleteAccountDialog v-if="deleteOpen" @close="deleteOpen = false" @deleted="onDeleted" />
    </template>
  </div>
</template>

<style scoped>
.settings {
  max-width: 880px;
  margin: 0 auto;
  padding: 24px 16px;
}
h1 {
  margin: 0 0 24px;
  font-size: 22px;
  font-weight: 500;
}
.row {
  display: grid;
  grid-template-columns: 200px minmax(0, 1fr);
  gap: 16px;
  padding: 16px 0;
}
.label {
  font-weight: 500;
}
.value input {
  width: 100%;
  max-width: 420px;
  padding: 10px 12px;
  border: 1px solid var(--border);
  border-radius: 8px;
  background: var(--bg);
  color: var(--text);
  font: inherit;
}
.value input:focus {
  outline: none;
  border-color: var(--link);
}
.hint {
  margin: 6px 0 0;
  overflow-wrap: anywhere;
}
.act {
  padding: 0;
  border: none;
  background: none;
  color: var(--link);
  font: inherit;
  font-weight: 500;
  cursor: pointer;
}
.act:hover {
  text-decoration: underline;
}
.act:disabled {
  opacity: 0.6;
  cursor: default;
}
@media (max-width: 600px) {
  .row {
    grid-template-columns: minmax(0, 1fr);
    gap: 6px;
  }
}
</style>