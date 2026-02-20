<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { uploadFile, getUploadStatus } from '@/api/upload'
import { approveCycle } from '@/api/approve'
import { useRagsStore } from '@/stores/rags'
import TaskProgress from '@/components/TaskProgress.vue'

const route = useRoute()
const ragsStore = useRagsStore()
const ragId = computed(() => Number(route.params.id))

const file = ref<File | null>(null)
const taskId = ref<number | null>(null)
const cycleId = ref<number | null>(null)
const uploadDone = ref(false)
const approved = ref(false)
const error = ref('')

onMounted(async () => {
  try {
    const status = await getUploadStatus(ragId.value)
    if (status.cycle_in_review) {
      cycleId.value = status.cycle_in_review.cycle_id
      taskId.value = status.cycle_in_review.task_id
      uploadDone.value = true
    }
  } catch {
    // RAG не найден или нет доступа — оставляем пустое состояние
  }
})

function onFileChange(e: Event) {
  const target = e.target as HTMLInputElement
  file.value = target.files?.[0] ?? null
}

async function doUpload() {
  if (!file.value) return
  error.value = ''
  try {
    const res = await uploadFile(ragId.value, file.value)
    cycleId.value = res.cycle_id
    taskId.value = res.task_id
  } catch (e: unknown) {
    const err = e as { response?: { data?: { detail?: string } } }
    error.value = err.response?.data?.detail ?? 'Ошибка загрузки'
  }
}

function onTaskDone() {
  uploadDone.value = true
}

function onTaskFailed(msg: string) {
  error.value = msg
}

async function doApprove() {
  if (cycleId.value == null) return
  error.value = ''
  try {
    await approveCycle(ragId.value, cycleId.value)
    approved.value = true
    await ragsStore.fetchCurrent(ragId.value)
  } catch (e: unknown) {
    const err = e as { response?: { data?: { detail?: string } } }
    error.value = err.response?.data?.detail ?? 'Ошибка'
  }
}
</script>

<template>
  <div class="upload-view">
    <h2>Загрузка файла</h2>
    <p v-if="!taskId">Выберите текстовый файл (.txt) и нажмите «Загрузить».</p>
    <div v-else>
      <TaskProgress :task-id="taskId" @done="onTaskDone" @failed="onTaskFailed" />
      <button v-if="uploadDone && !approved" @click="doApprove">Подтвердить цикл</button>
      <p v-if="approved">Цикл подтверждён.</p>
    </div>
    <div v-if="!taskId" class="upload-form">
      <input type="file" accept=".txt,text/plain" @change="onFileChange" />
      <button :disabled="!file" @click="doUpload">Загрузить</button>
    </div>
    <p v-if="error" class="error">{{ error }}</p>
  </div>
</template>

<style scoped>
.upload-view {
  max-width: 600px;
}
.upload-form {
  margin-top: 1rem;
}
.error {
  color: var(--vt-c-red);
  margin-top: 0.5rem;
}
</style>
