<template><AdminLedgerPage /></template>
<script setup lang="ts">
import AdminLedgerPage from '@/components/admin-ui/AdminLedgerPage.vue'
import { onLoad } from '@dcloudio/uni-app'
import { usePermission } from '@/composables/usePermission'
onLoad(() => requirePermission('finance.manage'))
</script>
