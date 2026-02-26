<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useRoute } from 'vue-router'
import {
  sendQuestion,
  getChatMessages,
  getSessions,
  createSession,
  getSessionMessages,
  updateSession,
  deleteSession,
  type ChatSessionListItem,
} from '@/api/chat'
import MessageBubble from '@/components/MessageBubble.vue'

const route = useRoute()
const ragId = computed(() => Number(route.params.id))

const question = ref('')
const loading = ref(false)
const sessions = ref<ChatSessionListItem[]>([])
const currentSessionId = ref<number | null>(null)
const messages = ref<{ id?: number; role: 'user' | 'assistant'; text: string; contextUsed?: number }[]>([])
const error = ref('')
const sessionsLoading = ref(true)
const editingSessionId = ref<number | null>(null)
const editTitle = ref('')

async function loadSessions() {
  try {
    const list = await getSessions(ragId.value)
    sessions.value = list
    if (list.length > 0 && currentSessionId.value === null) {
      currentSessionId.value = list[0]!.id
    }
  } catch {
    sessions.value = []
  } finally {
    sessionsLoading.value = false
  }
}

async function loadMessages() {
  try {
    if (currentSessionId.value != null) {
      const list = await getSessionMessages(ragId.value, currentSessionId.value)
      messages.value = list.map((m) => ({
        id: m.id,
        role: m.role as 'user' | 'assistant',
        text: m.content,
        contextUsed: m.context_used ?? undefined,
      }))
    } else {
      const list = await getChatMessages(ragId.value)
      messages.value = list.map((m) => ({
        id: m.id,
        role: m.role as 'user' | 'assistant',
        text: m.content,
        contextUsed: m.context_used ?? undefined,
      }))
    }
  } catch {
    messages.value = []
  }
}

onMounted(async () => {
  sessionsLoading.value = true
  await loadSessions()
  await loadMessages()
})

watch(currentSessionId, () => {
  loadMessages()
})

async function selectSession(id: number) {
  currentSessionId.value = id
}

async function newDialog() {
  try {
    const session = await createSession(ragId.value)
    sessions.value = [{ id: session.id, title: session.title, created_at: session.created_at }, ...sessions.value]
    currentSessionId.value = session.id
    messages.value = []
  } catch (e: unknown) {
    const err = e as { response?: { data?: { detail?: string } } }
    error.value = err.response?.data?.detail ?? 'Ошибка создания диалога'
  }
}

function startRename(s: ChatSessionListItem, e: Event) {
  e.stopPropagation()
  editingSessionId.value = s.id
  editTitle.value = s.title?.trim() ?? ''
}

function cancelRename() {
  editingSessionId.value = null
  editTitle.value = ''
}

async function saveRename(sessionId: number) {
  const title = editTitle.value.trim() || null
  try {
    await updateSession(ragId.value, sessionId, title)
    sessions.value = sessions.value.map((s) =>
      s.id === sessionId ? { ...s, title } : s
    )
    editingSessionId.value = null
    editTitle.value = ''
  } catch {
    error.value = 'Ошибка переименования'
    // поле остаётся открытым, можно повторить или отменить по Escape
  }
}

async function removeSession(sessionId: number, e: Event) {
  e.stopPropagation()
  if (editingSessionId.value === sessionId) cancelRename()
  if (!confirm('Удалить этот диалог и все сообщения?')) return
  try {
    await deleteSession(ragId.value, sessionId)
    sessions.value = sessions.value.filter((s) => s.id !== sessionId)
    if (currentSessionId.value === sessionId) {
      currentSessionId.value = sessions.value[0]?.id ?? null
      await loadMessages()
    }
  } catch {
    error.value = 'Ошибка удаления'
  }
}

function sessionTitle(s: ChatSessionListItem) {
  return s.title?.trim() || `Диалог ${s.id}`
}

async function ask() {
  if (!question.value.trim()) return
  const q = question.value.trim()
  question.value = ''
  messages.value.push({ role: 'user', text: q })
  loading.value = true
  error.value = ''
  try {
    const res = await sendQuestion(ragId.value, q, currentSessionId.value ?? undefined)
    messages.value.push({
      role: 'assistant',
      text: res.answer,
      contextUsed: res.context_used,
    })
    if (currentSessionId.value === null) {
      await loadSessions()
      if (sessions.value.length > 0) currentSessionId.value = sessions.value[0]!.id
    }
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
    <div class="chat-header">
      <h2>Диалог по RAG</h2>
      <div class="sessions-panel">
        <div class="sessions-label">Диалоги</div>
        <button type="button" class="btn-new" @click="newDialog">+ Новый диалог</button>
        <ul v-if="!sessionsLoading" class="sessions-list">
          <li
            v-for="s in sessions"
            :key="s.id"
            :class="{ active: currentSessionId === s.id }"
            @click="editingSessionId !== s.id && selectSession(s.id)"
          >
            <template v-if="editingSessionId === s.id">
              <input
                v-model="editTitle"
                type="text"
                class="session-edit-input"
                placeholder="Название диалога"
                @keydown.enter.prevent="saveRename(s.id)"
                @keydown.escape="cancelRename"
                @blur="saveRename(s.id)"
              />
            </template>
            <span v-else class="session-title">{{ sessionTitle(s) }}</span>
            <span v-if="editingSessionId !== s.id" class="session-actions">
              <button
                type="button"
                class="btn-rename-session"
                title="Переименовать"
                @click="startRename(s, $event)"
              >
                ✎
              </button>
              <button
                type="button"
                class="btn-delete-session"
                title="Удалить диалог"
                @click="removeSession(s.id, $event)"
              >
                ×
              </button>
            </span>
          </li>
        </ul>
        <p v-else class="sessions-loading">Загрузка…</p>
      </div>
    </div>
    <div class="messages">
      <MessageBubble
        v-for="(msg, i) in messages"
        :key="msg.id ?? `local-${i}`"
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
  max-width: 720px;
  display: flex;
  flex-direction: column;
}
.chat-header {
  display: flex;
  flex-wrap: wrap;
  gap: 1rem;
  align-items: flex-start;
  margin-bottom: 0.5rem;
}
.chat-header h2 {
  margin: 0;
}
.sessions-panel {
  flex: 1;
  min-width: 180px;
}
.sessions-label {
  font-size: 0.9rem;
  color: var(--vt-c-text-2);
  margin-bottom: 0.25rem;
}
.btn-new {
  padding: 0.35rem 0.6rem;
  font-size: 0.9rem;
  margin-bottom: 0.5rem;
}
.sessions-list {
  list-style: none;
  margin: 0;
  padding: 0;
}
.sessions-list li {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0.4rem 0.5rem;
  cursor: pointer;
  border-radius: 4px;
  gap: 0.5rem;
}
.sessions-list li:hover {
  background: var(--vt-c-bg-soft);
}
.sessions-list li.active {
  background: var(--vt-c-bg-soft);
  font-weight: 500;
}
.session-title {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 0.9rem;
}
.session-edit-input {
  flex: 1;
  min-width: 0;
  padding: 0.2rem 0.35rem;
  font-size: 0.9rem;
  border: 1px solid var(--vt-c-divider);
  border-radius: 3px;
}
.session-actions {
  flex-shrink: 0;
  display: flex;
  align-items: center;
  gap: 0.15rem;
}
.btn-rename-session {
  padding: 0.1rem 0.35rem;
  font-size: 0.95rem;
  line-height: 1;
  opacity: 0.7;
  border: none;
  background: transparent;
  cursor: pointer;
  border-radius: 3px;
}
.btn-rename-session:hover {
  opacity: 1;
  background: var(--vt-c-bg-soft);
}
.btn-delete-session {
  flex-shrink: 0;
  padding: 0.1rem 0.35rem;
  font-size: 1.1rem;
  line-height: 1;
  opacity: 0.7;
  border: none;
  background: transparent;
  cursor: pointer;
  border-radius: 3px;
}
.btn-delete-session:hover {
  opacity: 1;
  background: var(--vt-c-red-muted);
}
.sessions-loading {
  margin: 0;
  font-size: 0.9rem;
  color: var(--vt-c-text-2);
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
