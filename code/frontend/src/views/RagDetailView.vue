<script setup lang="ts">
import { onMounted, computed } from 'vue'
import { useRoute } from 'vue-router'
import { useRagsStore } from '@/stores/rags'

const route = useRoute()
const ragsStore = useRagsStore()
const ragId = computed(() => Number(route.params.id))

onMounted(() => ragsStore.fetchCurrent(ragId.value))

function tabTo(name: 'rag-upload' | 'rag-chat' | 'rag-members') {
  return { name, params: { id: route.params.id } }
}
</script>

<template>
  <div class="column q-gutter-md">
    <div v-if="ragsStore.current" class="text-h5 text-weight-medium">
      {{ ragsStore.current.name }}
    </div>
    <q-tabs
      dense
      align="left"
      active-color="primary"
      indicator-color="primary"
      class="q-mb-sm"
    >
      <q-route-tab :to="tabTo('rag-upload')" label="Загрузка" />
      <q-route-tab :to="tabTo('rag-chat')" label="Диалог" />
      <q-route-tab :to="tabTo('rag-members')" label="Участники" />
    </q-tabs>
    <router-view />
  </div>
</template>
