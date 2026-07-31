<template>
  <EmpHome v-if="auth.appMode === 'employee'" />
  <AdmDashboard v-else />
</template>
<script setup lang="ts">
import { onShow } from '@dcloudio/uni-app'
import { useAuthStore } from '@/stores/auth'
import { syncTabBarSelected } from '@/mixins/tabBar'
import EmpHome from '../emp-home/index.vue'
import AdmDashboard from '../adm-dashboard/index.vue'
const auth = useAuthStore()
onShow(() => syncTabBarSelected())
</script>
