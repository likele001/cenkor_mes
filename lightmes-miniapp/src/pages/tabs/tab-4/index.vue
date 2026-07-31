<template>
  <EmpProfile v-if="auth.appMode === 'employee'" />
  <AdmProfile v-else />
</template>
<script setup lang="ts">
import { onShow } from '@dcloudio/uni-app'
import { useAuthStore } from '@/stores/auth'
import { syncTabBarSelected, updateTabBarBadge } from '@/mixins/tabBar'
import EmpProfile from '../emp-profile/index.vue'
import AdmProfile from '../adm-profile/index.vue'
const auth = useAuthStore()
onShow(async () => {
  syncTabBarSelected()
  await auth.refreshUnread()
  updateTabBarBadge(auth.unreadCount)
})
</script>
