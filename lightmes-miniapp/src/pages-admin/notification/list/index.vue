<template><AdminNotificationPage /></template>
<script setup lang="ts">
import AdminNotificationPage from '@/components/admin-ui/AdminNotificationPage.vue'
import { onLoad } from '@dcloudio/uni-app'
import { usePermission } from '@/composables/usePermission'
const { requirePermission } = usePermission()
onLoad(() => requirePermission('notification.view'))
</script>
