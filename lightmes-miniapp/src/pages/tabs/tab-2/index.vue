<template>
  <EmpReport v-if="auth.appMode === 'employee'" />
  <AdmAudit v-else />
</template>
<script setup lang="ts">
import { onShow } from '@dcloudio/uni-app'
import { useAuthStore } from '@/stores/auth'
import { syncTabBarSelected } from '@/mixins/tabBar'
import EmpReport from '../emp-report/index.vue'
import AdmAudit from '../adm-audit/index.vue'
const auth = useAuthStore()
onShow(() => syncTabBarSelected())
</script>
