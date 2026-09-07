<!--
  Copyright (C) 2026 CenkorMES Project
  SPDX-License-Identifier: AGPL-3.0
-->
<template><AdminDictionaryPage /></template>
<script setup lang="ts">
import AdminDictionaryPage from '@/components/admin-ui/AdminDictionaryPage.vue'
import { onLoad } from '@dcloudio/uni-app'
import { usePermission } from '@/composables/usePermission'
onLoad(() => requirePermission('dict.manage'))
</script>
