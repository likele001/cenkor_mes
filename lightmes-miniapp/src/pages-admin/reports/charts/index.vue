<template><AdminReportsChartsPage /></template>
<script setup lang="ts">
import AdminReportsChartsPage from '@/components/admin-ui/AdminReportsChartsPage.vue'
import { onLoad } from '@dcloudio/uni-app'
import { usePermission } from '@/composables/usePermission'
const { requirePermission } = usePermission()
onLoad(() => requirePermission('report.view'))
</script>
