<template><AdminUserPage /></template>
<script setup lang="ts">
import AdminUserPage from '@/components/admin-ui/AdminUserPage.vue'
import { onLoad } from '@dcloudio/uni-app'
import { usePermission } from '@/composables/usePermission'
onLoad(() => requirePermission('user.manage'))
</script>
