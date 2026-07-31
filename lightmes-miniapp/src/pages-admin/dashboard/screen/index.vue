<template><AdminScreenPage /></template>
<script setup lang="ts">
import AdminScreenPage from '@/components/admin-ui/AdminScreenPage.vue'
import { onLoad } from '@dcloudio/uni-app'
import { usePermission } from '@/composables/usePermission'
const { requirePermission } = usePermission()
onLoad(() => requirePermission('dashboard.view'))
</script>
