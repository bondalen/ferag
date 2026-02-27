<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useRoute } from 'vue-router'
import { useQuasar } from 'quasar'
import {
  sendQuestion,
  getChatMessages,
  getSessionMessages,
} from '@/api/chat'
import type { ChatSessionListItem } from '@/api/chat'
import { useChatStore } from '@/stores/chat'
import MessageBubble from '@/components/MessageBubble.vue'

const route = useRoute()
const $q = useQuasar()
const chatStore = useChatStore()
const ragId = computed(() => Number(route.params.id))

const question = ref('')
const loading = ref(false)
const messages = ref<{ id?: number; role: 'user' | 'assistant'; text: string; contextUsed?: number }[]>([])
const error = ref('')
const editingSessionId = ref<number | null>(null)
const editTitle = ref('')

async function loadMessages() {
  try {
    if (chatStore.currentSessionId != null) {
      const list = await getSessionMessages(ragId.value, chatStore.currentSessionId)
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
  await chatStore.loadSessions(ragId.value)
  await loadMessages()
})

watch(() => chatStore.currentSessionId, () => {
  loadMessages()
})

function selectSession(id: number) {
  chatStore.setCurrentSession(id)
}

async function newDialog() {
  try {
    await chatStore.createSession(ragId.value)
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
  if (editingSessionId.value !== sessionId) return
  const title = editTitle.value.trim() || null
  try {
    await chatStore.updateSessionTitle(ragId.value, sessionId, title)
    editingSessionId.value = null
    editTitle.value = ''
  } catch {
    error.value = 'Ошибка переименования'
  }
}

function removeSession(sessionId: number, e: Event) {
  e.stopPropagation()
  if (editingSessionId.value === sessionId) cancelRename()
  $q.dialog({
    title: 'Удалить диалог',
    message: 'Удалить этот диалог и все сообщения?',
    cancel: true,
    persistent: true,
  }).onOk(async () => {
    try {
      await chatStore.removeSession(ragId.value, sessionId)
      await loadMessages()
    } catch {
      error.value = 'Ошибка удаления'
    }
  })
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
    const res = await sendQuestion(
      ragId.value,
      q,
      chatStore.currentSessionId ?? undefined
    )
    messages.value.push({
      role: 'assistant',
      text: res.answer,
      contextUsed: res.context_used,
    })
    if (chatStore.currentSessionId === null) {
      await chatStore.loadSessions(ragId.value)
      if (chatStore.sessions.length > 0) {
        chatStore.setCurrentSession(chatStore.sessions[0]!.id)
      }
    }
  } catch (e: unknown) {
    const err = e as { response?: { data?: { detail?: string } } }
    error.value = err.response?.data?.detail ?? 'Ошибка'
    messages.value.push({
      role: 'assistant',
      text: '(ошибка: ' + (error.value || 'неизвестная') + ')',
    })
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="column q-gutter-md chat-view">
    <div class="row q-col-gutter-md">
      <div class="col-12 col-sm-auto">
        <div class="text-h6 q-mb-sm">Диалог по RAG</div>
        <q-card flat bordered class="sessions-card">
          <q-card-section class="q-pa-sm">
            <div class="text-caption text-grey-7 q-mb-xs">Диалоги</div>
            <q-btn
              flat
              dense
              no-caps
              color="primary"
              icon="add"
              label="Новый диалог"
              class="q-mb-sm full-width"
              @click="newDialog"
            />
            <q-list v-if="!chatStore.sessionsLoading" bordered separator class="rounded-borders">
              <q-item
                v-for="s in chatStore.sessions"
                :key="s.id"
                :clickable="editingSessionId !== s.id"
                :active="chatStore.currentSessionId === s.id"
                active-class="bg-primary text-white"
                class="q-py-xs"
                @click="editingSessionId !== s.id && selectSession(s.id)"
              >
                <q-item-section>
                  <q-input
                    v-if="editingSessionId === s.id"
                    v-model="editTitle"
                    dense
                    outlined
                    placeholder="Название диалога"
                    class="session-edit-input"
                    @keydown.enter.prevent="saveRename(s.id)"
                    @keydown.escape="cancelRename"
                    @blur="saveRename(s.id)"
                  />
                  <q-item-label v-else class="text-body2 ellipsis">
                    {{ sessionTitle(s) }}
                  </q-item-label>
                </q-item-section>
                <q-item-section v-if="editingSessionId !== s.id" side>
                  <q-btn
                    flat
                    dense
                    round
                    size="sm"
                    icon="edit"
                    aria-label="Переименовать"
                    @click.stop="startRename(s, $event)"
                  />
                  <q-btn
                    flat
                    dense
                    round
                    size="sm"
                    icon="delete"
                    aria-label="Удалить"
                    color="negative"
                    @click.stop="removeSession(s.id, $event)"
                  />
                </q-item-section>
              </q-item>
            </q-list>
            <div v-else class="q-py-sm text-body2 text-grey-7">
              Загрузка…
            </div>
          </q-card-section>
        </q-card>
      </div>
      <div class="col">
        <div class="messages column q-gutter-sm">
          <MessageBubble
            v-for="(msg, i) in messages"
            :key="msg.id ?? `local-${i}`"
            :role="msg.role"
            :text="msg.text"
            :context-used="msg.contextUsed"
          />
        </div>
        <q-form class="column q-gutter-sm q-mt-md" @submit.prevent="ask">
          <div class="row q-col-gutter-sm">
            <q-input
              v-model="question"
              outlined
              dense
              placeholder="Вопрос..."
              class="col"
              :disable="loading"
            />
            <q-btn
              type="submit"
              color="primary"
              label="Отправить"
              no-caps
              :loading="loading"
              :disable="!question.trim()"
            />
          </div>
          <q-banner v-if="error" rounded class="bg-negative text-white">
            {{ error }}
          </q-banner>
        </q-form>
      </div>
    </div>
  </div>
</template>

<style scoped>
.chat-view {
  max-width: 900px;
}
.sessions-card {
  min-width: 220px;
}
.session-edit-input :deep(.q-field__control) {
  min-height: 32px;
}
.messages {
  min-height: 200px;
}
</style>
