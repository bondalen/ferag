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
  <q-btn
    flat
    no-caps
    :to="{ name: 'home' }"
    class="q-mr-md text-white text-weight-bold"
  >
    ferag
  </q-btn>
  <q-space />
  <span v-if="auth.user" class="q-mr-sm text-white">{{ auth.user.email }}</span>
  <q-btn
    v-if="auth.user"
    flat
    dense
    label="Выйти"
    class="text-white"
    @click="logout"
  />
</template>
