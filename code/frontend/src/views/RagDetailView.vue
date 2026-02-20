<script setup lang="ts">
import { onMounted, computed } from 'vue'
import { useRoute } from 'vue-router'
import { useRagsStore } from '@/stores/rags'
import NavBar from '@/components/NavBar.vue'

const route = useRoute()
const ragsStore = useRagsStore()
const ragId = computed(() => Number(route.params.id))

onMounted(() => ragsStore.fetchCurrent(ragId.value))
</script>

<template>
  <NavBar />
  <div class="rag-detail">
    <h1 v-if="ragsStore.current">{{ ragsStore.current.name }}</h1>
    <nav class="tabs">
      <router-link :to="{ name: 'rag-upload', params: { id: ragId } }" active-class="active">Загрузка</router-link>
      <router-link :to="{ name: 'rag-chat', params: { id: ragId } }" active-class="active">Диалог</router-link>
      <router-link :to="{ name: 'rag-members', params: { id: ragId } }" active-class="active">Участники</router-link>
    </nav>
    <router-view />
  </div>
</template>

<style scoped>
.rag-detail {
  padding: 1.5rem;
}
.tabs {
  display: flex;
  gap: 1rem;
  margin-bottom: 1rem;
}
.tabs a.active {
  font-weight: bold;
  text-decoration: none;
}
</style>
