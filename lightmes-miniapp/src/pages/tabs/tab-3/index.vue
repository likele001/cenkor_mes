<template>
  <EmpAttendance v-if="auth.appMode === 'employee'" />
  <AdmMessage v-else />
</template>
<script setup lang="ts">
import { onShow } from '@dcloudio/uni-app'
import { useAuthStore } from '@/stores/auth'
import { syncTabBarSelected } from '@/mixins/tabBar'
import EmpAttendance from '../emp-attendance/index.vue'
import AdmMessage from '../adm-message/index.vue'
const auth = useAuthStore()
onShow(() => syncTabBarSelected())
</script>
