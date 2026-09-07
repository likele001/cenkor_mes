<!--
  Copyright (C) 2026 CenkorMES Project
  SPDX-License-Identifier: AGPL-3.0
-->
<template>
  <AdminTaskAssignPage :initial-task-id="initialTaskId" />
</template>
<script setup lang="ts">
import { ref } from 'vue'
import { onLoad } from '@dcloudio/uni-app'
import AdminTaskAssignPage from '@/components/admin-ui/AdminTaskAssignPage.vue'
import { usePermission } from '@/composables/usePermission'

const { requirePermission } = usePermission()
const initialTaskId = ref<number | null>(null)

onLoad((q) => {
  requirePermission('dispatch.manage')
  const id = Number(q?.taskId || 0)
  initialTaskId.value = id > 0 ? id : null
})
</script>
