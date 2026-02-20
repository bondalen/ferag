<script setup lang="ts">
import { ref, computed } from 'vue'
import { useRoute } from 'vue-router'
import { sendQuestion } from '@/api/chat'
import MessageBubble from '@/components/MessageBubble.vue'

const route = useRoute()
const ragId = computed(() => Number(route.params.id))

const question = ref('')
const loading = ref(false)
const messages = ref<{ role: 'user' | 'assistant'; text: string; contextUsed?: number }[]>([])
const error = ref('')

async function ask() {
  if (!question.value.trim()) return
  const q = question.value.trim()
  question.value = ''
  messages.value.push({ role: 'user', text: q })
  loading.value = true
  error.value = ''
  try {
    const res = await sendQuestion(ragId.value, q)
    messages.value.push({
      role: 'assistant',
      text: res.answer,
      contextUsed: res.context_used,
    })
  } catch (e: unknown) {
    const err = e as { response?: { data?: { detail?: string } } }
    error.value = err.response?.data?.detail ?? 'Ошибка'
    messages.value.push({ role: 'assistant', text: '(ошибка: ' + (error.value || 'неизвестная') + ')' })
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="chat-view">
    <h2>Диалог по RAG</h2>
    <div class="messages">
      <MessageBubble
        v-for="(msg, i) in messages"
        :key="i"
        :role="msg.role"
        :text="msg.text"
        :context-used="msg.contextUsed"
      />
    </div>
    <form @submit.prevent="ask" class="chat-form">
      <input v-model="question" type="text" placeholder="Вопрос..." :disabled="loading" />
      <button :disabled="loading">Отправить</button>
    </form>
    <p v-if="error" class="error">{{ error }}</p>
  </div>
</template>

<style scoped>
.chat-view {
  max-width: 640px;
}
.messages {
  margin-bottom: 1rem;
  min-height: 200px;
}
.chat-form {
  display: flex;
  gap: 0.5rem;
}
.chat-form input {
  flex: 1;
  padding: 0.5rem;
}
.error {
  color: var(--vt-c-red);
  margin-top: 0.5rem;
}
</style>
