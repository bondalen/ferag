<script setup lang="ts">
import { ref } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import NavBar from '@/components/NavBar.vue'

const router = useRouter()
const route = useRoute()
const auth = useAuthStore()

const mode = ref<'login' | 'register'>('login')
const email = ref('')
const password = ref('')
const displayName = ref('')
const error = ref('')

async function submit() {
  error.value = ''
  try {
    if (mode.value === 'login') {
      await auth.login(email.value, password.value)
    } else {
      const { register } = await import('@/api/auth')
      await register({
        email: email.value,
        password: password.value,
        display_name: displayName.value || undefined,
      })
      await auth.login(email.value, password.value)
    }
    const redirect = (route.query.redirect as string) || '/'
    await router.push(redirect)
  } catch (e: unknown) {
    const err = e as { response?: { data?: { detail?: string } } }
    error.value = err.response?.data?.detail ?? 'Ошибка'
  }
}
</script>

<template>
  <NavBar />
  <div class="login-page">
    <form @submit.prevent="submit" class="login-form">
      <h1>{{ mode === 'login' ? 'Вход' : 'Регистрация' }}</h1>
      <input v-model="email" type="email" placeholder="Email" required />
      <input v-model="password" type="password" placeholder="Пароль" required />
      <input
        v-if="mode === 'register'"
        v-model="displayName"
        type="text"
        placeholder="Имя (необязательно)"
      />
      <p v-if="error" class="error">{{ error }}</p>
      <button type="submit">{{ mode === 'login' ? 'Войти' : 'Зарегистрироваться' }}</button>
      <button type="button" class="link" @click="mode = mode === 'login' ? 'register' : 'login'">
        {{ mode === 'login' ? 'Нет аккаунта? Регистрация' : 'Уже есть аккаунт? Вход' }}
      </button>
    </form>
  </div>
</template>

<style scoped>
.login-page {
  padding: 2rem;
  display: flex;
  justify-content: center;
}
.login-form {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
  max-width: 320px;
}
.login-form input {
  padding: 0.5rem;
}
.login-form .error {
  color: var(--vt-c-red);
}
.login-form .link {
  background: none;
  border: none;
  color: var(--vt-c-brand-1);
  cursor: pointer;
  text-decoration: underline;
}
</style>
