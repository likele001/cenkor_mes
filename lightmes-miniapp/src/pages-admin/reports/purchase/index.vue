<!--
  Copyright (C) 2026 CenkorMES Project
  SPDX-License-Identifier: AGPL-3.0
-->
<template><AdminPurchaseStatsPage /></template>
<script setup lang="ts">
import AdminPurchaseStatsPage from '@/components/admin-ui/AdminPurchaseStatsPage.vue'
import { onLoad } from '@dcloudio/uni-app'
import { usePermission } from '@/composables/usePermission'
const { requirePermission } = usePermission()
onLoad(() => requirePermission('report.view'))
</script>
