<template><AdminSettingsPage /></template>
<script setup lang="ts">
import AdminSettingsPage from '@/components/admin-ui/AdminSettingsPage.vue'
import { onLoad } from '@dcloudio/uni-app'
import { usePermission } from '@/composables/usePermission'
onLoad(() => requirePermission('setting.manage'))
</script>
