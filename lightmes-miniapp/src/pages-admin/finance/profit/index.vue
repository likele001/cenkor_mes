<!--
  Copyright (C) 2026 CenkorMES Project
  SPDX-License-Identifier: AGPL-3.0
-->
<template><AdminProfitPage /></template>
<script setup lang="ts">
import AdminProfitPage from '@/components/admin-ui/AdminProfitPage.vue'
import { onLoad } from '@dcloudio/uni-app'
import { usePermission } from '@/composables/usePermission'
onLoad(() => requirePermission('finance.manage'))
</script>
