<!--
  Copyright (C) 2026 CenkorMES Project
  SPDX-License-Identifier: AGPL-3.0
-->
<template><AdminFinanceStatementPage /></template>
<script setup lang="ts">
import AdminFinanceStatementPage from '@/components/admin-ui/AdminFinanceStatementPage.vue'
import { onLoad } from '@dcloudio/uni-app'
import { usePermission } from '@/composables/usePermission'
onLoad(() => requirePermission('finance.manage'))
</script>
