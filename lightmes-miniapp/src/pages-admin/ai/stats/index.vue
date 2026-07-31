<template>
  <AdminAiStatsPage />
</template>

<script setup lang="ts">
import AdminAiStatsPage from '@/components/admin-ui/AdminAiStatsPage.vue'
import { onLoad } from '@dcloudio/uni-app'
import { usePermission } from '@/composables/usePermission'

const { requirePermission } = usePermission()
onLoad(() => requirePermission('ai.use'))
</script>
