<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useRagsStore } from '@/stores/rags'
import * as ragsApi from '@/api/rags'

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
    const rag = await ragsApi.createRag({
      name: name.value.trim(),
      description: description.value.trim() || undefined,
    })
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
  <div class="column q-gutter-md">
    <q-card flat bordered>
      <q-card-section>
        <div class="text-h6 q-mb-md">Создать RAG</div>
        <q-form class="column q-gutter-sm" @submit.prevent="createRag">
          <div class="row q-col-gutter-sm">
            <q-input
              v-model="name"
              label="Название"
              outlined
              dense
              class="col-xs-12 col-sm-auto"
              style="min-width: 200px"
              :disable="creating"
            />
            <q-input
              v-model="description"
              label="Описание (необязательно)"
              outlined
              dense
              class="col-xs-12 col-sm"
              :disable="creating"
            />
          </div>
          <q-banner v-if="error" rounded class="bg-negative text-white">
            {{ error }}
          </q-banner>
          <q-btn
            type="submit"
            label="Создать"
            color="primary"
            no-caps
            :loading="creating"
            :disable="!name.trim()"
          />
        </q-form>
      </q-card-section>
    </q-card>

    <q-card flat bordered>
      <q-card-section>
        <div class="text-h6 q-mb-md">Мои RAG</div>
        <q-list v-if="ragsStore.list.length" bordered separator>
          <q-item
            v-for="rag in ragsStore.list"
            :key="rag.id"
            clickable
            :to="{ name: 'rag-detail', params: { id: String(rag.id) } }"
          >
            <q-item-section>
              <q-item-label>{{ rag.name }}</q-item-label>
              <q-item-label caption>Циклов: {{ rag.cycle_count }}</q-item-label>
            </q-item-section>
            <q-item-section side>
              <q-icon name="chevron_right" />
            </q-item-section>
          </q-item>
        </q-list>
        <div v-else class="text-body2 text-grey-7 q-py-md">
          Нет RAG. Создайте первый выше.
        </div>
      </q-card-section>
    </q-card>
  </div>
</template>
