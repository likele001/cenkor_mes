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
