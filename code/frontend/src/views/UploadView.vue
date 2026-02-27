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

// QFile без multiple отдаёт File | null, не массив
const fileList = ref<File | File[] | null>(null)
const taskId = ref<number | null>(null)
const cycleId = ref<number | null>(null)
const uploadDone = ref(false)
const approved = ref(false)
const error = ref('')
const uploading = ref(false)

const hasFile = computed(() => {
  const v = fileList.value
  return Array.isArray(v) ? v.length > 0 : v != null
})
const file = computed((): File | null => {
  const v = fileList.value
  return Array.isArray(v) ? (v[0] ?? null) : (v ?? null)
})

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

function onTaskDone() {
  uploadDone.value = true
}

function onTaskFailed(msg: string) {
  error.value = msg
}

async function doUpload() {
  const f = file.value
  if (!f) return
  error.value = ''
  uploading.value = true
  try {
    const res = await uploadFile(ragId.value, f)
    cycleId.value = res.cycle_id
    taskId.value = res.task_id
    fileList.value = null
  } catch (e: unknown) {
    const err = e as { response?: { data?: { detail?: string } } }
    error.value = err.response?.data?.detail ?? 'Ошибка загрузки'
  } finally {
    uploading.value = false
  }
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
  <div class="column q-gutter-md upload-view">
    <q-card flat bordered>
      <q-card-section>
        <div class="text-h6 q-mb-sm">Загрузка файла</div>
        <p v-if="!taskId" class="text-body2 text-grey-8 q-mb-md">
          Выберите текстовый файл (.txt) и нажмите «Загрузить».
        </p>
        <template v-else>
          <TaskProgress :task-id="taskId" @done="onTaskDone" @failed="onTaskFailed" />
          <q-btn
            v-if="uploadDone && !approved"
            color="primary"
            label="Подтвердить цикл"
            no-caps
            class="q-mt-sm"
            @click="doApprove"
          />
          <q-banner v-if="approved" rounded class="bg-positive text-white q-mt-sm">
            Цикл подтверждён.
          </q-banner>
        </template>
        <div v-if="!taskId" class="column q-gutter-sm q-mt-md">
          <q-file
            v-model="fileList"
            outlined
            dense
            label="Файл .txt"
            accept=".txt,text/plain"
            clearable
            :disable="uploading"
          />
          <q-btn
            color="primary"
            label="Загрузить"
            no-caps
            :loading="uploading"
            :disable="!hasFile"
            @click="doUpload"
          />
        </div>
        <q-banner v-if="error" rounded class="bg-negative text-white q-mt-md">
          {{ error }}
        </q-banner>
      </q-card-section>
    </q-card>
  </div>
</template>

<style scoped>
.upload-view {
  max-width: 600px;
}
</style>
