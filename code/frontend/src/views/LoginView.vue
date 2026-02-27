<script setup lang="ts">
import { ref } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

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
  <div class="row justify-center q-pt-lg">
    <q-card flat bordered class="login-card q-pa-md">
      <q-card-section>
        <div class="text-h5 q-mb-md">{{ mode === 'login' ? 'Вход' : 'Регистрация' }}</div>
        <q-form class="column q-gutter-md" @submit.prevent="submit">
          <q-input
            v-model="email"
            type="email"
            label="Email"
            outlined
            dense
            required
            autocomplete="email"
          />
          <q-input
            v-model="password"
            type="password"
            label="Пароль"
            outlined
            dense
            required
            autocomplete="current-password"
          />
          <q-input
            v-if="mode === 'register'"
            v-model="displayName"
            type="text"
            label="Имя (необязательно)"
            outlined
            dense
            autocomplete="name"
          />
          <q-banner v-if="error" rounded class="bg-negative text-white q-mt-sm">
            {{ error }}
          </q-banner>
          <q-btn
            type="submit"
            :label="mode === 'login' ? 'Войти' : 'Зарегистрироваться'"
            color="primary"
            no-caps
            class="q-mt-sm"
          />
          <q-btn
            flat
            no-caps
            color="primary"
            :label="mode === 'login' ? 'Нет аккаунта? Регистрация' : 'Уже есть аккаунт? Вход'"
            @click="mode = mode === 'login' ? 'register' : 'login'"
          />
        </q-form>
      </q-card-section>
    </q-card>
  </div>
</template>

<style scoped>
.login-card {
  max-width: 400px;
  width: 100%;
}
</style>
