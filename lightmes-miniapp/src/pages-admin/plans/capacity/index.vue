<template><AdminCapacityPage /></template>
<script setup lang="ts">
import AdminCapacityPage from '@/components/admin-ui/AdminCapacityPage.vue'
import { onLoad } from '@dcloudio/uni-app'
import { usePermission } from '@/composables/usePermission'
onLoad(() => requirePermission('plan.manage'))
</script>
