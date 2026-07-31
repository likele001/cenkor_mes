<template><AdminTaskListPage /></template>
<script setup lang="ts">
import AdminTaskListPage from '@/components/admin-ui/AdminTaskListPage.vue'
import { onLoad } from '@dcloudio/uni-app'
import { usePermission } from '@/composables/usePermission'
const { requirePermission } = usePermission()
onLoad(() => requirePermission('task.manage'))
</script>
