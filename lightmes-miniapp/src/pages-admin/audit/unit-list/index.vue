<template><AdminAuditUnitPage /></template>
<script setup lang="ts">
import AdminAuditUnitPage from '@/components/admin-ui/AdminAuditUnitPage.vue'
import { onLoad } from '@dcloudio/uni-app'
import { onPullDownRefresh } from '@dcloudio/uni-app'
import { usePermission } from '@/composables/usePermission'
const { requirePermission } = usePermission()
onLoad(() => requirePermission('report.audit'))

onPullDownRefresh(() => {
  load().finally(() => uni.stopPullDownRefresh())
})

</script>
