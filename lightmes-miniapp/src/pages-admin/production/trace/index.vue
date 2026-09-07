<!--
  Copyright (C) 2026 CenkorMES Project
  SPDX-License-Identifier: AGPL-3.0
-->
<template><AdminTracePage /></template>
<script setup lang="ts">
import AdminTracePage from '@/components/admin-ui/AdminTracePage.vue'
import { onLoad } from '@dcloudio/uni-app'
import { usePermission } from '@/composables/usePermission'
const { requirePermission } = usePermission()
onLoad(() => requirePermission('trace.query'))
</script>
