<script setup>
import { ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import AuthLayout from '../components/AuthLayout.vue'
import { useAuth } from '../composables/useAuth'
import { safeNext } from '../composables/redirect'

const { register } = useAuth()
const router = useRouter()
const route = useRoute()

const email = ref('')
const username = ref('')
const password = ref('')
const error = ref('')
const busy = ref(false)

async function submit() {
  error.value = ''
  busy.value = true
  try {
    await register(email.value.trim(), username.value.trim(), password.value)
    router.push(safeNext(route.query.next))
  } catch (e) {
    error.value = e.message
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <AuthLayout title="Регистрация">
    <form @submit.prevent="submit">
      <label class="field">
        <span>Email</span>
        <input v-model="email" type="email" autocomplete="email" required />
      </label>
      <label class="field">
        <span>Имя пользователя</span>
        <input
          v-model="username"
          autocomplete="username"
          required
          pattern="[A-Za-z0-9_]{3,30}"
          title="3–30 символов: латинские буквы, цифры, _"
        />
      </label>
      <label class="field">
        <span>Пароль (от 8 символов)</span>
        <input
          v-model="password"
          type="password"
          autocomplete="new-password"
          required
          minlength="8"
          maxlength="128"
        />
      </label>
      <p v-if="error" class="error" role="alert">{{ error }}</p>
      <button class="btn btn-primary" :disabled="busy">
        {{ busy ? 'Создаём…' : 'Создать аккаунт' }}
      </button>
    </form>
    <template #footer>
      Уже есть аккаунт? <RouterLink to="/login">Войти</RouterLink>
    </template>
  </AuthLayout>
</template>