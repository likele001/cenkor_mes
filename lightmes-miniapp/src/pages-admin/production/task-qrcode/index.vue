<template>
  <AdminTaskQrcodePage />
</template>
<script setup lang="ts">
import AdminTaskQrcodePage from '@/components/admin-ui/AdminTaskQrcodePage.vue'
import { onLoad } from '@dcloudio/uni-app'
import { usePermission } from '@/composables/usePermission'
const { requirePermission } = usePermission()
onLoad(() => requirePermission('dispatch.manage'))
</script>
