<template><AdminSalaryPage /></template>
<script setup lang="ts">
import AdminSalaryPage from '@/components/admin-ui/AdminSalaryPage.vue'
import { onLoad } from '@dcloudio/uni-app'
import { usePermission } from '@/composables/usePermission'
onLoad(() => requirePermission('salary.manage'))
</script>
