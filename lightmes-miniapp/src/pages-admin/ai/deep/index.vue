<template>
  <AdminAiDeepPage />
</template>

<script setup lang="ts">
import AdminAiDeepPage from '@/components/admin-ui/AdminAiDeepPage.vue'
import { onLoad } from '@dcloudio/uni-app'
import { usePermission } from '@/composables/usePermission'

const { requirePermission } = usePermission()
onLoad(() => requirePermission('ai.use'))
</script>
