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
    <p v-for="(s, i) in steps" :key="i" :class="s.status">
      {{ s.step || s.status }} <span v-if="s.error">{{ s.error }}</span>
    </p>
  </div>
</template>

<style scoped>
.task-progress p {
  margin: 0.25rem 0;
  font-size: 0.9rem;
}
.task-progress p.done {
  color: var(--vt-c-green);
}
.task-progress p.failed {
  color: var(--vt-c-red);
}
</style>
