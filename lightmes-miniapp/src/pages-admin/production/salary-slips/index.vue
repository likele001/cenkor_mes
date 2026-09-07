<!--
  Copyright (C) 2026 CenkorMES Project
  SPDX-License-Identifier: AGPL-3.0
-->
<template><AdminSalarySlipsPage /></template>
<script setup lang="ts">
import AdminSalarySlipsPage from '@/components/admin-ui/AdminSalarySlipsPage.vue'
import { onLoad } from '@dcloudio/uni-app'
import { usePermission } from '@/composables/usePermission'
const { requirePermission } = usePermission()
onLoad(() => requirePermission('salary.manage'))
</script>
