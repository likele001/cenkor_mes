<template>
  <EmpTasks v-if="auth.appMode === 'employee'" />
  <AdmWork v-else />
</template>
<script setup lang="ts">
import { onShow } from '@dcloudio/uni-app'
import { useAuthStore } from '@/stores/auth'
import { syncTabBarSelected } from '@/mixins/tabBar'
import EmpTasks from '../emp-tasks/index.vue'
import AdmWork from '../adm-work/index.vue'
const auth = useAuthStore()
onShow(() => syncTabBarSelected())
</script>
