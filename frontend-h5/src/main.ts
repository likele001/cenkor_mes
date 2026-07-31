import { createApp } from 'vue'
import { createPinia } from 'pinia'
import Vant from 'vant'
import 'vant/lib/index.css'
import './style.css'
import App from './App.vue'
import router from './router'
import { i18n, getStoredLocale } from '@/locales'
import { applyVantLocale } from '@/utils/vant-locale'
import { installChunkReloadHandlers } from '@/utils/chunk-reload'

applyVantLocale(getStoredLocale())
installChunkReloadHandlers()

const app = createApp(App)
app.use(createPinia())
app.use(Vant)
app.use(router)
app.use(i18n)
app.mount('#app')
