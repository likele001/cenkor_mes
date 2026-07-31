import { createApp } from 'vue'
import ElementPlus from 'element-plus'
import zhCn from 'element-plus/es/locale/lang/zh-cn'
import en from 'element-plus/es/locale/lang/en'
import ko from 'element-plus/es/locale/lang/ko'
import 'element-plus/dist/index.css'
import 'element-plus/theme-chalk/dark/css-vars.css'
import { createPinia } from 'pinia'
import { initAdminTheme } from '@/composables/useAdminTheme'
import { i18n, getStoredLocale } from '@/locales'
import './style.css'
import App from './App.vue'
import router from './router'
import { installChunkReloadHandlers } from '@/utils/chunk-reload'

initAdminTheme()
installChunkReloadHandlers()

function getElementPlusLocale(locale: string) {
  switch (locale) {
    case 'en-US': return en
    case 'ko-KR': return ko
    default: return zhCn
  }
}

const app = createApp(App)
app.use(createPinia())
app.use(router)
app.use(i18n)
app.use(ElementPlus, { locale: getElementPlusLocale(getStoredLocale()) })
app.mount('#app')
