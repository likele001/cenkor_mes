<template>
  <AdminAutomationPage />
</template>

<script setup lang="ts">
import AdminAutomationPage from '@/components/admin-ui/AdminAutomationPage.vue'
import { onLoad } from '@dcloudio/uni-app'
import { usePermission } from '@/composables/usePermission'

const { requirePermission } = usePermission()
onLoad(() => requirePermission('setting.manage'))
</script>
