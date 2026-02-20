import { defineStore } from 'pinia'
import { ref } from 'vue'
import * as ragsApi from '@/api/rags'
import type { Rag } from '@/api/rags'

export const useRagsStore = defineStore('rags', () => {
  const list = ref<Rag[]>([])
  const current = ref<Rag | null>(null)

  async function fetchList(): Promise<void> {
    list.value = await ragsApi.listRags()
  }

  async function fetchCurrent(id: number): Promise<void> {
    current.value = await ragsApi.getRag(id)
  }

  function clearCurrent(): void {
    current.value = null
  }

  return { list, current, fetchList, fetchCurrent, clearCurrent }
})
