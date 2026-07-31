<template>
  <AdminStockPage />
</template>
<script setup lang="ts">
import AdminStockPage from '@/components/admin-ui/AdminStockPage.vue'
import { onLoad } from '@dcloudio/uni-app'
import { usePermission } from '@/composables/usePermission'
const { requirePermission } = usePermission()
onLoad(() => requirePermission('warehouse.manage'))
</script>
