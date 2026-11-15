import { ref } from 'vue'

// Список с курсорной пагинацией. fetchPage(cursor) -> { items, next_cursor }
export function usePagedList(fetchPage) {
  const items = ref([])
  const loading = ref(false)
  const done = ref(false)
  const error = ref('')
  let cursor = null
  let generation = 0 // reset() обнуляет поколение: ответы на устаревшие запросы отбрасываются

  async function loadMore() {
    if (loading.value || done.value) return
    const gen = generation
    loading.value = true
    error.value = ''
    try {
      const page = await fetchPage(cursor)
      if (gen !== generation) return
      items.value.push(...page.items)
      cursor = page.next_cursor
      if (cursor === null) done.value = true
    } catch (e) {
      if (gen === generation) error.value = e.message
    } finally {
      if (gen === generation) loading.value = false
    }
  }

  function reset() {
    generation++
    items.value = []
    cursor = null
    done.value = false
    loading.value = false
    error.value = ''
  }

  return { items, loading, done, error, loadMore, reset }
}