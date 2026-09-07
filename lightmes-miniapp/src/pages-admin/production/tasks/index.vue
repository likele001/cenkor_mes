<!--
  Copyright (C) 2026 CenkorMES Project
  SPDX-License-Identifier: AGPL-3.0
-->
<template><AdminTaskListPage /></template>
<script setup lang="ts">
import AdminTaskListPage from '@/components/admin-ui/AdminTaskListPage.vue'
import { onLoad } from '@dcloudio/uni-app'
import { usePermission } from '@/composables/usePermission'
const { requirePermission } = usePermission()
onLoad(() => requirePermission('task.manage'))
</script>
