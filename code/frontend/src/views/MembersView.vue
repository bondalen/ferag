<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { useQuasar } from 'quasar'
import { listMembers, addMember, removeMember } from '@/api/members'
import type { MemberListItem } from '@/api/members'
import { useRagsStore } from '@/stores/rags'
import { useAuthStore } from '@/stores/auth'

const route = useRoute()
const $q = useQuasar()
const ragsStore = useRagsStore()
const authStore = useAuthStore()
const ragId = computed(() => Number(route.params.id))

const members = ref<MemberListItem[]>([])
const email = ref('')
const role = ref<'viewer' | 'editor'>('viewer')
const loading = ref(false)
const error = ref('')

const roleOptions = [
  { label: 'viewer', value: 'viewer' as const },
  { label: 'editor', value: 'editor' as const },
]

const isOwner = computed(
  () => ragsStore.current && authStore.user && ragsStore.current.owner_id === authStore.user.id
)

onMounted(() => loadMembers())

async function loadMembers() {
  try {
    members.value = await listMembers(ragId.value)
  } catch {
    error.value = 'Не удалось загрузить список'
  }
}

async function doAdd() {
  if (!email.value.trim()) return
  loading.value = true
  error.value = ''
  try {
    await addMember(ragId.value, { email: email.value.trim(), role: role.value })
    email.value = ''
    await loadMembers()
  } catch (e: unknown) {
    const err = e as { response?: { data?: { detail?: string } } }
    error.value = err.response?.data?.detail ?? 'Ошибка'
  } finally {
    loading.value = false
  }
}

function doRemove(userId: number) {
  $q.dialog({
    title: 'Удалить участника',
    message: 'Удалить этого участника из RAG?',
    cancel: true,
    persistent: true,
  }).onOk(async () => {
    error.value = ''
    try {
      await removeMember(ragId.value, userId)
      await loadMembers()
    } catch (e: unknown) {
      const err = e as { response?: { data?: { detail?: string } } }
      error.value = err.response?.data?.detail ?? 'Ошибка'
    }
  })
}
</script>

<template>
  <div class="column q-gutter-md members-view">
    <q-card flat bordered>
      <q-card-section>
        <div class="text-h6 q-mb-md">Участники</div>
        <q-list v-if="members.length" bordered separator class="rounded-borders">
          <q-item v-for="m in members" :key="m.user_id">
            <q-item-section>
              <q-item-label>{{ m.email }}</q-item-label>
              <q-item-label caption>{{ m.role }}</q-item-label>
            </q-item-section>
            <q-item-section v-if="m.role !== 'owner' && isOwner" side>
              <q-btn
                flat
                dense
                no-caps
                color="negative"
                label="Удалить"
                size="sm"
                @click="doRemove(m.user_id)"
              />
            </q-item-section>
          </q-item>
        </q-list>
        <p v-else class="text-body2 text-grey-7">Нет участников кроме владельца.</p>
        <div v-if="isOwner" class="column q-gutter-sm q-mt-md">
          <div class="row q-col-gutter-sm items-end">
            <q-input
              v-model="email"
              type="email"
              label="Email"
              outlined
              dense
              class="col"
              :disable="loading"
            />
            <q-select
              v-model="role"
              :options="roleOptions"
              option-value="value"
              option-label="label"
              emit-value
              map-options
              outlined
              dense
              label="Роль"
              class="col-auto"
              style="min-width: 120px"
              :disable="loading"
            />
            <q-btn
              color="primary"
              label="Добавить"
              no-caps
              :loading="loading"
              :disable="!email.trim()"
              @click="doAdd"
            />
          </div>
        </div>
        <q-banner v-if="error" rounded class="bg-negative text-white q-mt-md">
          {{ error }}
        </q-banner>
      </q-card-section>
    </q-card>
  </div>
</template>

<style scoped>
.members-view {
  max-width: 600px;
}
</style>
