<template><AdminPurchaseStatsPage /></template>
<script setup lang="ts">
import AdminPurchaseStatsPage from '@/components/admin-ui/AdminPurchaseStatsPage.vue'
import { onLoad } from '@dcloudio/uni-app'
import { usePermission } from '@/composables/usePermission'
const { requirePermission } = usePermission()
onLoad(() => requirePermission('report.view'))
</script>
