import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import { clearToken, getToken, setToken } from '@/api/request'
import { fetchMe, type MeOut } from '@/api/auth'
import { apiGet } from '@/api/request'

export const useAuthStore = defineStore('auth', () => {
  const token = ref(getToken())
  const userInfo = ref<MeOut | null>(null)
  const unreadCount = ref(0)

  const roles = computed(() => userInfo.value?.roles ?? [])
  const permissions = computed(() => userInfo.value?.permissions ?? [])

  const isEmployee = computed(
    () => roles.value.includes('employee') || roles.value.includes('leader'),
  )

  function hasPermission(code: string): boolean {
    if (userInfo.value?.is_superuser) return true
    return permissions.value.includes(code)
  }

  async function saveToken(t: string) {
    token.value = t
    setToken(t)
  }

  async function fetchUser() {
    if (!token.value) return null
    try {
      const data = await fetchMe(false)
      userInfo.value = data
      return data
    } catch {
      userInfo.value = null
      return null
    }
  }

  async function refreshUnread() {
    if (!token.value) {
      unreadCount.value = 0
      return
    }
    try {
      const d = await apiGet<{ count: number }>('/h5/notifications/unread-count')
      unreadCount.value = d?.count ?? 0
    } catch {
      unreadCount.value = 0
    }
  }

  function logout() {
    token.value = ''
    userInfo.value = null
    unreadCount.value = 0
    clearToken()
    uni.reLaunch({ url: '/pages/shared/login/index' })
  }

  return {
    token,
    userInfo,
    unreadCount,
    roles,
    permissions,
    isEmployee,
    hasPermission,
    saveToken,
    fetchUser,
    refreshUnread,
    logout,
  }
})
