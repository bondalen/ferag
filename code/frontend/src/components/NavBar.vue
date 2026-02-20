<script setup lang="ts">
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const router = useRouter()
const auth = useAuthStore()

function logout() {
  auth.logout()
  router.push({ name: 'login' })
}
</script>

<template>
  <nav class="navbar">
    <router-link to="/" class="brand">ferag</router-link>
    <span v-if="auth.user" class="user">{{ auth.user.email }}</span>
    <button v-if="auth.user" type="button" @click="logout">Выйти</button>
  </nav>
</template>

<style scoped>
.navbar {
  display: flex;
  align-items: center;
  gap: 1rem;
  padding: 0.75rem 1.5rem;
  border-bottom: 1px solid var(--vt-c-divider-light-1);
}
.brand {
  font-weight: bold;
  text-decoration: none;
  color: inherit;
}
.user {
  margin-left: auto;
  font-size: 0.9rem;
  color: var(--vt-c-text-2);
}
</style>
