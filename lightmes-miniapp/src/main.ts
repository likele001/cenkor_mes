// Copyright (C) 2026 CenkorMES Project
// SPDX-License-Identifier: AGPL-3.0
import { createSSRApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'
import { i18n } from '@/locales'

export function createApp() {
  const app = createSSRApp(App)
  app.use(createPinia())
  app.use(i18n)
  return { app }
}
