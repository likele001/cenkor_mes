<!--
  Copyright (C) 2026 CenkorMES Project
  SPDX-License-Identifier: AGPL-3.0
-->
<template><AdminSettingsPage /></template>
<script setup lang="ts">
import AdminSettingsPage from '@/components/admin-ui/AdminSettingsPage.vue'
import { onLoad } from '@dcloudio/uni-app'
import { usePermission } from '@/composables/usePermission'
onLoad(() => requirePermission('setting.manage'))
</script>
