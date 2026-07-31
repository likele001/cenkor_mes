import { onBeforeUnmount, ref, watch } from 'vue'
import { onBeforeRouteLeave } from 'vue-router'
import { useI18n } from 'vue-i18n'

const STORAGE_KEY_PREFIX = 'cenkormes-unsaved-form:'

export function useUnsavedGuard(formKey: string) {
  const { t } = useI18n()
  const isDirty = ref(false)

  function markDirty() {
    isDirty.value = true
  }

  function markClean() {
    isDirty.value = false
    clearStorage()
  }

  function saveToStorage(data: Record<string, unknown>) {
    try {
      sessionStorage.setItem(STORAGE_KEY_PREFIX + formKey, JSON.stringify(data))
    } catch {
      // 存储上限忽略
    }
  }

  function loadFromStorage(): Record<string, unknown> | null {
    try {
      const raw = sessionStorage.getItem(STORAGE_KEY_PREFIX + formKey)
      return raw ? JSON.parse(raw) : null
    } catch {
      return null
    }
  }

  function clearStorage() {
    sessionStorage.removeItem(STORAGE_KEY_PREFIX + formKey)
  }

  // 路由离开拦截
  onBeforeRouteLeave((_to, _from, next) => {
    if (isDirty.value) {
      const confirmed = window.confirm(t('common.unsavedConfirm') || '有未保存的修改，确定离开？')
      if (!confirmed) {
        next(false)
        return
      }
    }
    next()
  })

  // 浏览器关闭/刷新拦截
  function handleBeforeUnload(e: BeforeUnloadEvent) {
    if (isDirty.value) {
      e.preventDefault()
      e.returnValue = ''
    }
  }
  window.addEventListener('beforeunload', handleBeforeUnload)
  onBeforeUnmount(() => {
    window.removeEventListener('beforeunload', handleBeforeUnload)
  })

  return { isDirty, markDirty, markClean, saveToStorage, loadFromStorage, clearStorage }
}
