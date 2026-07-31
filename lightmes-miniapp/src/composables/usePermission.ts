import { computed } from 'vue'
import { useAuthStore } from '@/stores/auth'

export function usePermission() {
  const auth = useAuthStore()

  const canAccessEmployee = computed(() => auth.isEmployee)

  function hasPermission(code: string): boolean {
    return auth.hasPermission(code)
  }

  function requirePermission(code: string, back = true): boolean {
    if (hasPermission(code)) return true
    uni.showToast({ title: '无权限访问', icon: 'none' })
    if (back) {
      setTimeout(() => uni.navigateBack({ fail: () => uni.switchTab({ url: '/pages/tabs/emp-home/index' }) }), 500)
    }
    return false
  }

  function requireEmployee(): boolean {
    if (canAccessEmployee.value) return true
    uni.showToast({ title: '仅员工可访问', icon: 'none' })
    return false
  }

  return {
    canAccessEmployee,
    hasPermission,
    requirePermission,
    requireEmployee,
  }
}
