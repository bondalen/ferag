import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import {
  getSessions,
  createSession as apiCreateSession,
  updateSession as apiUpdateSession,
  deleteSession as apiDeleteSession,
  type ChatSessionListItem,
} from '@/api/chat'

/** Сохранённая выбранная сессия по ragId (ключ — строка ragId, значение — sessionId). Персистится в localStorage. */
export type SessionByRag = Record<string, number>

export const useChatStore = defineStore(
  'chat',
  () => {
    const currentRagId = ref<number | null>(null)
    const sessions = ref<ChatSessionListItem[]>([])
    const currentSessionId = ref<number | null>(null)
    const sessionsLoading = ref(false)
    /** Выбранная сессия по RAG (ragId -> sessionId); персистится плагином. */
    const sessionByRag = ref<SessionByRag>({})

    const hasSessions = computed(() => sessions.value.length > 0)

    async function loadSessions(ragId: number): Promise<void> {
      if (currentRagId.value !== ragId) {
        currentRagId.value = ragId
        currentSessionId.value = null
        sessions.value = []
      }
      sessionsLoading.value = true
      try {
        const list = await getSessions(ragId)
        sessions.value = list
        const key = String(ragId)
        const savedId = sessionByRag.value[key]
        if (savedId != null && list.some((s) => s.id === savedId)) {
          currentSessionId.value = savedId
        } else if (list.length > 0) {
          currentSessionId.value = list[0]!.id
          sessionByRag.value = { ...sessionByRag.value, [key]: list[0]!.id }
        } else {
          currentSessionId.value = null
        }
      } catch {
        sessions.value = []
      } finally {
        sessionsLoading.value = false
      }
    }

    function setCurrentSession(id: number | null): void {
      currentSessionId.value = id
      if (currentRagId.value != null) {
        const key = String(currentRagId.value)
        if (id != null) {
          sessionByRag.value = { ...sessionByRag.value, [key]: id }
        } else {
          const next = { ...sessionByRag.value }
          delete next[key]
          sessionByRag.value = next
        }
      }
    }

  async function createSession(ragId: number, title?: string | null): Promise<ChatSessionListItem> {
    const session = await apiCreateSession(ragId, title)
    const item: ChatSessionListItem = {
      id: session.id,
      title: session.title,
      created_at: session.created_at,
    }
    sessions.value = [item, ...sessions.value]
    currentSessionId.value = session.id
    sessionByRag.value = { ...sessionByRag.value, [String(ragId)]: session.id }
    return item
  }

  async function updateSessionTitle(
    ragId: number,
    sessionId: number,
    title: string | null
  ): Promise<void> {
    await apiUpdateSession(ragId, sessionId, title)
    sessions.value = sessions.value.map((s) =>
      s.id === sessionId ? { ...s, title } : s
    )
  }

  async function removeSession(ragId: number, sessionId: number): Promise<void> {
    await apiDeleteSession(ragId, sessionId)
    sessions.value = sessions.value.filter((s) => s.id !== sessionId)
    const key = String(ragId)
    if (currentSessionId.value === sessionId) {
      currentSessionId.value = sessions.value[0]?.id ?? null
      if (currentSessionId.value != null) {
        sessionByRag.value = { ...sessionByRag.value, [key]: currentSessionId.value }
      } else {
        const next = { ...sessionByRag.value }
        delete next[key]
        sessionByRag.value = next
      }
    }
  }

    return {
      currentRagId,
      sessions,
      currentSessionId,
      sessionsLoading,
      sessionByRag,
      hasSessions,
      loadSessions,
      setCurrentSession,
      createSession,
      updateSessionTitle,
      removeSession,
    }
  },
  {
    persist: {
      key: 'ferag.chat.sessionByRag',
      pick: ['sessionByRag'],
    },
  }
)
