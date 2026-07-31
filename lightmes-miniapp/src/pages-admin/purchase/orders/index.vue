<template>
  <AdminPurchaseOrderPage />
</template>

<script setup lang="ts">
import AdminPurchaseOrderPage from '@/components/admin-ui/AdminPurchaseOrderPage.vue'
import { onLoad } from '@dcloudio/uni-app'
import { usePermission } from '@/composables/usePermission'

const { requirePermission } = usePermission()
onLoad(() => requirePermission('purchase.manage'))
</script>
