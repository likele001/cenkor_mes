<!--
  Copyright (C) 2026 CenkorMES Project
  SPDX-License-Identifier: AGPL-3.0
-->
<template>
  <el-config-provider :locale="epLocale">
    <router-view />
  </el-config-provider>
</template>

<script setup lang="ts">
import { onMounted, watch } from 'vue'
import zhCn from 'element-plus/es/locale/lang/zh-cn'
import en from 'element-plus/es/locale/lang/en'
import ko from 'element-plus/es/locale/lang/ko'
import { useAppConfigStore } from '@/stores/app-config'
import { getStoredLocale } from '@/locales'

// Element Plus 内置文案语言（启动时确定，无运行时切换）
function resolveElementPlusLocale(locale: string) {
  switch (locale) {
    case 'en-US': return en
    case 'ko-KR': return ko
    default: return zhCn
  }
}
const epLocale = resolveElementPlusLocale(getStoredLocale())

const appConfig = useAppConfigStore()

onMounted(() => appConfig.load())

watch(() => appConfig.browserTitle, (title) => {
  document.title = title
})
</script>
