<!--
  Copyright (C) 2026 CenkorMES Project
  SPDX-License-Identifier: AGPL-3.0
-->
<template>
  <router-view />
</template>

<script setup lang="ts">
import { onMounted, watch } from 'vue'
import { useAppConfigStore } from '@/stores/app-config'

const appConfig = useAppConfigStore()

onMounted(() => appConfig.load())

watch(() => appConfig.browserTitle, (title) => {
  document.title = title
})
</script>
