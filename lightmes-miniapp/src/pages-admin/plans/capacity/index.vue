<!--
  Copyright (C) 2026 CenkorMES Project
  SPDX-License-Identifier: AGPL-3.0
-->
<template><AdminCapacityPage /></template>
<script setup lang="ts">
import AdminCapacityPage from '@/components/admin-ui/AdminCapacityPage.vue'
import { onLoad } from '@dcloudio/uni-app'
import { usePermission } from '@/composables/usePermission'
onLoad(() => requirePermission('plan.manage'))
</script>
