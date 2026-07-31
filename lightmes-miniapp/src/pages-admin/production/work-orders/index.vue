<template><AdminWorkOrderPage /></template>
<script setup lang="ts">
import AdminWorkOrderPage from '@/components/admin-ui/AdminWorkOrderPage.vue'
import { onLoad } from '@dcloudio/uni-app'
import { usePermission } from '@/composables/usePermission'
const { requirePermission } = usePermission()
onLoad(() => requirePermission('work.manage'))
</script>
