<template><AdminProfitPage /></template>
<script setup lang="ts">
import AdminProfitPage from '@/components/admin-ui/AdminProfitPage.vue'
import { onLoad } from '@dcloudio/uni-app'
import { usePermission } from '@/composables/usePermission'
onLoad(() => requirePermission('finance.manage'))
</script>
