import { ref } from 'vue'
import { api } from '../api/client'

const categories = ref([])
let loading = null

// Справочник маленький и не меняется, грузим один раз на всё приложение
function ensure() {
  if (!loading) {
    loading = api.categories
      .list()
      .then((list) => {
        categories.value = list
      })
      .catch(() => {
        loading = null // повторим при следующем использовании
      })
  }
  return loading
}

const nameById = (id) => categories.value.find((c) => c.id === id)?.name ?? ''
const defaultId = () => categories.value.find((c) => c.slug === 'other')?.id ?? null

export function useCategories() {
  ensure()
  return { categories, nameById, defaultId }
}