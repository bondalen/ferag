<script setup lang="ts">
defineProps<{
  role: 'user' | 'assistant'
  text: string
  contextUsed?: number
}>()
</script>

<template>
  <div :class="['bubble', role]">
    <p class="text">{{ text }}</p>
    <p v-if="role === 'assistant' && contextUsed != null" class="meta">Контекст: {{ contextUsed }} фрагментов</p>
  </div>
</template>

<style scoped>
.bubble {
  max-width: 85%;
  padding: 0.75rem 1rem;
  margin-bottom: 0.75rem;
  border-radius: 1rem;
}
.bubble.user {
  margin-left: 0;
  margin-right: auto;
  background: var(--vt-c-brand-1);
  color: var(--vt-c-bg-soft);
}
.bubble.assistant {
  margin-left: auto;
  margin-right: 0;
  background: var(--vt-c-bg-soft);
  border: 1px solid var(--vt-c-divider-light-1);
}
.meta {
  font-size: 0.8rem;
  color: var(--vt-c-text-3);
  margin-top: 0.5rem;
  margin-bottom: 0;
}
.text {
  margin: 0;
  white-space: pre-wrap;
}
</style>
