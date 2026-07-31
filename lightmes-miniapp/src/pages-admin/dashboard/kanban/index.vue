<template><AdminKanbanPage /></template>
<script setup lang="ts">
import AdminKanbanPage from '@/components/admin-ui/AdminKanbanPage.vue'
import { onLoad } from '@dcloudio/uni-app'
import { usePermission } from '@/composables/usePermission'
const { requirePermission } = usePermission()
onLoad(() => requirePermission('dashboard.view'))
</script>
