<template><AdminOpportunityStatsPage /></template>
<script setup lang="ts">
import AdminOpportunityStatsPage from '@/components/admin-ui/AdminOpportunityStatsPage.vue'
import { onLoad } from '@dcloudio/uni-app'
import { usePermission } from '@/composables/usePermission'
const { requirePermission } = usePermission()
onLoad(() => requirePermission('customer.manage'))
</script>
