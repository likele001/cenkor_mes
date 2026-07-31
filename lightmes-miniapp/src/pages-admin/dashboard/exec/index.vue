<template><AdminExecDashboardPage /></template>
<script setup lang="ts">
import AdminExecDashboardPage from '@/components/admin-ui/AdminExecDashboardPage.vue'
import { onLoad } from '@dcloudio/uni-app'
import { usePermission } from '@/composables/usePermission'
const { requirePermission } = usePermission()
onLoad(() => requirePermission('exec_dashboard.view'))
</script>
