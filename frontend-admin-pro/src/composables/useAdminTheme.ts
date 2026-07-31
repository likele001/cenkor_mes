import { computed, ref, watch } from 'vue'

export type AdminTheme = 'light' | 'dark'

const STORAGE_KEY = 'cenkormes-admin-theme'

const theme = ref<AdminTheme>('light')
let initialized = false

function readPreferredTheme(): AdminTheme {
  const saved = localStorage.getItem(STORAGE_KEY) as AdminTheme | null
  if (saved === 'light' || saved === 'dark') return saved
  return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
}

function applyTheme(t: AdminTheme) {
  document.documentElement.classList.remove('light', 'dark')
  document.documentElement.classList.add(t)
  document.documentElement.dataset.adminTheme = t
  localStorage.setItem(STORAGE_KEY, t)
}

export function initAdminTheme() {
  if (initialized) return
  theme.value = readPreferredTheme()
  applyTheme(theme.value)
  initialized = true
}

export function useAdminTheme() {
  if (!initialized && typeof window !== 'undefined') {
    initAdminTheme()
  }

  watch(theme, (t) => applyTheme(t), { immediate: false })

  function toggleTheme() {
    theme.value = theme.value === 'light' ? 'dark' : 'light'
    applyTheme(theme.value)
  }

  function setTheme(t: AdminTheme) {
    theme.value = t
    applyTheme(t)
  }

  return {
    theme,
    toggleTheme,
    setTheme,
    isDark: computed(() => theme.value === 'dark'),
  }
}
