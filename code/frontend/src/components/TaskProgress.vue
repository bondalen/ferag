<script setup lang="ts">
import { ref, onMounted, onUnmounted, watch } from 'vue'
import { useAuthStore } from '@/stores/auth'
import { getStoredToken } from '@/api/client'

const props = defineProps<{ taskId: number }>()
const emit = defineEmits<{ done: []; failed: [msg: string] }>()

const authStore = useAuthStore()
const steps = ref<{ status: string; step: string; error: string | null }[]>([])
let ws: WebSocket | null = null

function getWsUrl(): string {
  const token = authStore.token ?? getStoredToken()
  const id = props.taskId
  if (typeof window === 'undefined') return ''
  const isDev = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1'
  if (isDev) {
    return `ws://localhost:47821/ws/tasks/${id}?token=${token ?? ''}`
  }
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  const host = window.location.host
  return `${protocol}//${host}/ferag/ws/tasks/${id}?token=${token ?? ''}`
}

function connect() {
  const url = getWsUrl()
  if (!url) return
  ws = new WebSocket(url)
  ws.onmessage = (e) => {
    // { status, step, error } — план 6.3
    const msg = JSON.parse(e.data) as { status: string; step: string; error: string | null }
    steps.value.push(msg)
    if (msg.status === 'done') emit('done')
    if (msg.status === 'failed') emit('failed', msg.error ?? 'Unknown error')
  }
  ws.onerror = () => {
    steps.value.push({ status: 'failed', step: '', error: 'WebSocket error' })
  }
}

function close() {
  if (ws) {
    ws.close()
    ws = null
  }
}

onMounted(connect)
onUnmounted(close)
watch(() => props.taskId, () => {
  close()
  steps.value = []
  connect()
})
</script>

<template>
  <div class="task-progress">
    <div v-if="steps.length === 0" class="row items-center q-gutter-sm text-body2 text-grey-7">
      <q-spinner size="20" />
      <span>Подключение…</span>
    </div>
    <q-list v-else bordered separator class="rounded-borders">
      <q-item
        v-for="(s, i) in steps"
        :key="i"
        class="q-py-xs"
        :class="s.status === 'done' ? 'text-positive' : s.status === 'failed' ? 'text-negative' : 'text-grey-7'"
      >
        <q-item-section side>
          <q-icon
            :name="s.status === 'done' ? 'check_circle' : s.status === 'failed' ? 'error' : 'schedule'"
            :color="s.status === 'done' ? 'positive' : s.status === 'failed' ? 'negative' : 'grey'"
            size="sm"
          />
        </q-item-section>
        <q-item-section>
          <q-item-label class="text-body2">
            {{ s.step || s.status }}
            <span v-if="s.error" class="q-ml-sm">{{ s.error }}</span>
          </q-item-label>
        </q-item-section>
      </q-item>
    </q-list>
  </div>
</template>

<style scoped>
.task-progress {
  max-width: 100%;
}
</style>
