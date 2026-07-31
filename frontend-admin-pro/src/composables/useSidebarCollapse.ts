import { onMounted, ref, watch } from 'vue'

const STORAGE_KEY = 'cenkormes-admin-sider-collapsed'

export function useSidebarCollapse() {
  const collapsed = ref(false)

  onMounted(() => {
    collapsed.value = localStorage.getItem(STORAGE_KEY) === '1'
  })

  watch(collapsed, (v) => {
    localStorage.setItem(STORAGE_KEY, v ? '1' : '0')
  })

  function toggleCollapse() {
    collapsed.value = !collapsed.value
  }

  return { collapsed, toggleCollapse }
}
