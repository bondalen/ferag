<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { listMembers, addMember, removeMember } from '@/api/members'
import type { MemberListItem } from '@/api/members'
import { useRagsStore } from '@/stores/rags'
import { useAuthStore } from '@/stores/auth'

const route = useRoute()
const ragsStore = useRagsStore()
const authStore = useAuthStore()
const ragId = computed(() => Number(route.params.id))

const members = ref<MemberListItem[]>([])
const email = ref('')
const role = ref<'viewer' | 'editor'>('viewer')
const loading = ref(false)
const error = ref('')

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

async function doRemove(userId: number) {
  if (!confirm('Удалить участника?')) return
  error.value = ''
  try {
    await removeMember(ragId.value, userId)
    await loadMembers()
  } catch (e: unknown) {
    const err = e as { response?: { data?: { detail?: string } } }
    error.value = err.response?.data?.detail ?? 'Ошибка'
  }
}

const isOwner = computed(
  () => ragsStore.current && authStore.user && ragsStore.current.owner_id === authStore.user.id
)
</script>

<template>
  <div class="members-view">
    <h2>Участники</h2>
    <ul class="member-list">
      <li v-for="m in members" :key="m.user_id" class="member-item">
        <span>{{ m.email }} — {{ m.role }}</span>
        <button
          v-if="m.role !== 'owner' && isOwner"
          type="button"
          class="remove-btn"
          @click="doRemove(m.user_id)"
        >
          Удалить
        </button>
      </li>
    </ul>
    <div v-if="isOwner" class="add-form">
      <input v-model="email" type="email" placeholder="Email" />
      <select v-model="role">
        <option value="viewer">viewer</option>
        <option value="editor">editor</option>
      </select>
      <button :disabled="loading" @click="doAdd">Добавить</button>
    </div>
    <p v-if="error" class="error">{{ error }}</p>
  </div>
</template>

<style scoped>
.member-list {
  list-style: none;
  padding: 0;
}
.member-item {
  display: flex;
  align-items: center;
  gap: 1rem;
  margin-bottom: 0.5rem;
}
.remove-btn {
  font-size: 0.85rem;
  padding: 0.25rem 0.5rem;
}
.add-form {
  margin-top: 1rem;
  display: flex;
  gap: 0.5rem;
  flex-wrap: wrap;
}
.error {
  color: var(--vt-c-red);
  margin-top: 0.5rem;
}
</style>
