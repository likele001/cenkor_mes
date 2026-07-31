<template><AdminPurchaseStatementPage /></template>
<script setup lang="ts">
import AdminPurchaseStatementPage from '@/components/admin-ui/AdminPurchaseStatementPage.vue'
import { onLoad } from '@dcloudio/uni-app'
import { usePermission } from '@/composables/usePermission'
onLoad(() => requirePermission('purchase.manage'))
</script>
