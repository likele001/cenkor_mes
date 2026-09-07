<!--
  Copyright (C) 2026 CenkorMES Project
  SPDX-License-Identifier: AGPL-3.0
-->
<template><AdminCrmPoolPage /></template>
<script setup lang="ts">
import AdminCrmPoolPage from '@/components/admin-ui/AdminCrmPoolPage.vue'
import { onLoad } from '@dcloudio/uni-app'
import { usePermission } from '@/composables/usePermission'
onLoad(() => requirePermission('customer.manage'))
</script>
