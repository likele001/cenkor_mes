<template><AdminDictionaryPage /></template>
<script setup lang="ts">
import AdminDictionaryPage from '@/components/admin-ui/AdminDictionaryPage.vue'
import { onLoad } from '@dcloudio/uni-app'
import { usePermission } from '@/composables/usePermission'
onLoad(() => requirePermission('dict.manage'))
</script>
