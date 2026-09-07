<!--
  Copyright (C) 2026 CenkorMES Project
  SPDX-License-Identifier: AGPL-3.0
-->
<template><AdminExecDashboardPage /></template>
<script setup lang="ts">
import AdminExecDashboardPage from '@/components/admin-ui/AdminExecDashboardPage.vue'
import { onLoad } from '@dcloudio/uni-app'
import { usePermission } from '@/composables/usePermission'
const { requirePermission } = usePermission()
onLoad(() => requirePermission('exec_dashboard.view'))
</script>
