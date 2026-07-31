import { computed, reactive, ref } from 'vue'

export type OffsetLimitQuery = {
  offset: number
  limit: number
}

export function useListPage<T extends OffsetLimitQuery>(initialQuery: T) {
  const loading = ref(false)
  const query = reactive({ ...initialQuery }) as T

  const page = computed(() => Math.floor(query.offset / query.limit) + 1)

  function estimateTotal(itemCount: number) {
    return query.offset + itemCount + (itemCount === query.limit ? query.limit : 0)
  }

  function onPageChange(p: number) {
    query.offset = (p - 1) * query.limit
  }

  function resetOffset() {
    query.offset = 0
  }

  async function runReload(reset: boolean, loader: (q: T) => Promise<void>) {
    if (reset) resetOffset()
    loading.value = true
    try {
      await loader(query)
    } finally {
      loading.value = false
    }
  }

  return {
    loading,
    query,
    page,
    estimateTotal,
    onPageChange,
    resetOffset,
    runReload,
  }
}
