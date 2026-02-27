<script setup lang="ts">
defineProps<{
  role: 'user' | 'assistant'
  text: string
  contextUsed?: number
}>()
</script>

<template>
  <div class="row" :class="role === 'user' ? 'justify-start' : 'justify-end'">
    <q-card
      flat
      :bordered="role === 'assistant'"
      :class="[
        'message-bubble q-pa-md',
        role === 'user' ? 'bg-primary text-white' : 'bg-grey-3'
      ]"
    >
      <p class="text-body2 q-my-none message-bubble__text">{{ text }}</p>
      <p
        v-if="role === 'assistant' && contextUsed != null"
        class="text-caption q-mt-sm q-mb-none text-grey-7"
      >
        Контекст: {{ contextUsed }} фрагментов
      </p>
    </q-card>
  </div>
</template>

<style scoped>
.message-bubble {
  max-width: 85%;
  border-radius: 1rem;
}
.message-bubble__text {
  white-space: pre-wrap;
}
</style>
