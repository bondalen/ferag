<script setup lang="ts">
import { onMounted, onUnmounted } from 'vue'
import { RouterView, useRouter } from 'vue-router'
import NavBar from '@/components/NavBar.vue'
import { useAuthStore } from '@/stores/auth'

const router = useRouter()
function onUnauthorized() {
  useAuthStore().logout()
  router.push({ name: 'login', query: { redirect: router.currentRoute.value.fullPath } })
}

onMounted(() => {
  window.addEventListener('ferag:unauthorized', onUnauthorized)
})
onUnmounted(() => {
  window.removeEventListener('ferag:unauthorized', onUnauthorized)
})
</script>

<template>
  <q-layout view="hHh lpR fFf">
    <q-header elevated class="bg-primary text-white">
      <q-toolbar>
        <NavBar />
      </q-toolbar>
    </q-header>

    <q-page-container>
      <q-page class="q-pa-md">
        <RouterView />
      </q-page>
    </q-page-container>
  </q-layout>
</template>

<style>
#app {
  min-height: 100vh;
}
</style>
