<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useRagsStore } from '@/stores/rags'
import * as ragsApi from '@/api/rags'
import NavBar from '@/components/NavBar.vue'

const router = useRouter()
const ragsStore = useRagsStore()
const name = ref('')
const description = ref('')
const creating = ref(false)
const error = ref('')

onMounted(() => ragsStore.fetchList())

async function createRag() {
  if (!name.value.trim()) return
  creating.value = true
  error.value = ''
  try {
    const rag = await ragsApi.createRag({ name: name.value.trim(), description: description.value.trim() || undefined })
    await ragsStore.fetchList()
    name.value = ''
    description.value = ''
    await router.push({ name: 'rag-detail', params: { id: String(rag.id) } })
  } catch (e: unknown) {
    const err = e as { response?: { data?: { detail?: string } } }
    error.value = err.response?.data?.detail ?? 'Ошибка'
  } finally {
    creating.value = false
  }
}
</script>

<template>
  <NavBar />
  <div class="rags-page">
    <section class="create-form">
      <h2>Создать RAG</h2>
      <input v-model="name" type="text" placeholder="Название" />
      <input v-model="description" type="text" placeholder="Описание (необязательно)" />
      <p v-if="error" class="error">{{ error }}</p>
      <button :disabled="creating" @click="createRag">Создать</button>
    </section>
    <section class="rag-list">
      <h2>Мои RAG</h2>
      <ul v-if="ragsStore.list.length">
        <li v-for="rag in ragsStore.list" :key="rag.id">
          <router-link :to="{ name: 'rag-detail', params: { id: String(rag.id) } }">
            {{ rag.name }} (циклов: {{ rag.cycle_count }})
          </router-link>
        </li>
      </ul>
      <p v-else>Нет RAG. Создайте первый выше.</p>
    </section>
  </div>
</template>

<style scoped>
.rags-page {
  padding: 1.5rem;
}
.create-form,
.rag-list {
  margin-bottom: 2rem;
}
.create-form input,
.create-form button {
  margin-right: 0.5rem;
  margin-bottom: 0.5rem;
}
.rag-list ul {
  list-style: none;
  padding: 0;
}
.rag-list li {
  margin-bottom: 0.5rem;
}
.error {
  color: var(--vt-c-red);
}
</style>
