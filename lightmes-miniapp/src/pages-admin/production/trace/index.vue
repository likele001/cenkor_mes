<template><AdminTracePage /></template>
<script setup lang="ts">
import AdminTracePage from '@/components/admin-ui/AdminTracePage.vue'
import { onLoad } from '@dcloudio/uni-app'
import { usePermission } from '@/composables/usePermission'
const { requirePermission } = usePermission()
onLoad(() => requirePermission('trace.query'))
</script>
