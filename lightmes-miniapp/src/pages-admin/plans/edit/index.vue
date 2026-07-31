<template>
  <AdminPlanPage />
</template>

<script setup lang="ts">
import AdminPlanPage from '@/components/admin-ui/AdminPlanPage.vue'
import { onLoad } from '@dcloudio/uni-app'
import { usePermission } from '@/composables/usePermission'

const { requirePermission } = usePermission()
onLoad(() => requirePermission('plan.manage'))
</script>
