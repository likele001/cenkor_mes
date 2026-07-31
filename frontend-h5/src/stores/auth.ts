import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import { getMyUnreadNotificationCount } from '@/api/tasks'
import { me as meApi, type MeOut } from '@/api/auth'

import { clearAuthToken, getAuthToken, setAuthToken } from '@/utils/session-token'

const TOKEN_KEY = 'cenkormes_token'

export const useAuthStore = defineStore('auth', () => {
  const token = ref(getAuthToken(TOKEN_KEY) || '')
  const userInfo = ref<Pick<MeOut, 'full_name' | 'roles' | 'username' | 'phone' | 'email'> | null>(null)
  const permissions = ref<string[]>([])
  const unreadNotificationCount = ref(0)

  const roles = computed(() => userInfo.value?.roles ?? [])
  const isCustomer = computed(() => roles.value.includes('customer'))
  const isEmployee = computed(() => roles.value.includes('employee') || roles.value.includes('leader'))

  function hasPermission(code: string) {
    return permissions.value.includes(code)
  }

  function hasAnyPermission(codes: string[]) {
    return codes.some((c) => permissions.value.includes(c))
  }

  function setToken(newToken: string, remember = false) {
    token.value = newToken
    setAuthToken(TOKEN_KEY, newToken, remember)
  }

  async function fetchMe() {
    if (!token.value) return
    try {
      const data = await meApi()
      userInfo.value = {
        full_name: data.full_name,
        roles: data.roles,
        username: data.username,
        phone: data.phone,
        email: data.email,
      }
      permissions.value = data.permissions || []
    } catch {
      userInfo.value = null
      permissions.value = []
    }
  }

  async function refreshUnreadNotificationCount() {
    if (!token.value) {
      unreadNotificationCount.value = 0
      return
    }
    try {
      const resp = await getMyUnreadNotificationCount()
      unreadNotificationCount.value = resp?.count ?? 0
    } catch {
      unreadNotificationCount.value = 0
    }
  }

  function logout() {
    token.value = ''
    userInfo.value = null
    permissions.value = []
    unreadNotificationCount.value = 0
    clearAuthToken(TOKEN_KEY)
  }

  return {
    token,
    userInfo,
    permissions,
    roles,
    isCustomer,
    isEmployee,
    unreadNotificationCount,
    hasPermission,
    hasAnyPermission,
    setToken,
    fetchMe,
    refreshUnreadNotificationCount,
    logout,
  }
})
