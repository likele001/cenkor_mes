// Copyright (C) 2026 CenkorMES Project
// SPDX-License-Identifier: AGPL-3.0
import * as Vue from 'vue'
import { createApp } from 'vue'
// Element Plus 改为按需引入：模板组件与指令由 unplugin-vue-components 自动引入并注入样式。
// 编程式 API（ElMessage / ElMessageBox）在各文件显式 import，样式需在此手动引入副作用。
import 'element-plus/es/components/message/style/css'
import 'element-plus/es/components/message-box/style/css'
// 暗色主题 CSS 变量为全局能力，需保留
import 'element-plus/theme-chalk/dark/css-vars.css'
import { createPinia } from 'pinia'
import { initAdminTheme } from '@/composables/useAdminTheme'
import { i18n } from '@/locales'
import './style.css'
import App from './App.vue'
import router from './router'
import { installChunkReloadHandlers } from '@/utils/chunk-reload'
import { setupExtensionLoader } from '@/utils/extensionLoader'

initAdminTheme()
installChunkReloadHandlers()

// 扩展宿主运行时：向插件脚本暴露共享 Vue 运行时，并安装插件注册桥
window.Vue = Vue
setupExtensionLoader({ router })

const app = createApp(App)
app.use(createPinia())
app.use(router)
app.use(i18n)
app.mount('#app')
