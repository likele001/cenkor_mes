<template><AdminCrmPoolPage /></template>
<script setup lang="ts">
import AdminCrmPoolPage from '@/components/admin-ui/AdminCrmPoolPage.vue'
import { onLoad } from '@dcloudio/uni-app'
import { usePermission } from '@/composables/usePermission'
onLoad(() => requirePermission('customer.manage'))
</script>
