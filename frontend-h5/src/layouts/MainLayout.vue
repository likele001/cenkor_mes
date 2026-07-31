<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { useAuthStore } from '@/stores/auth'
import { getStoredTenantCode } from '@/utils/tenant'
import { setStoredLocale, type AppLocale } from '@/locales'
import { applyVantLocale } from '@/utils/vant-locale'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const { t, locale } = useI18n()

const showLangSheet = ref(false)

const title = computed(() => {
  void locale.value
  const key = route.meta?.titleKey as string | undefined
  if (key) return t(key)
  return (route.meta?.title as string) || '辰科MES'
})

const langActions = computed(() => [
  { name: t('common.zhCN'), value: 'zh-CN' as AppLocale },
  { name: t('common.enUS'), value: 'en-US' as AppLocale },
  { name: t('common.koKR'), value: 'ko-KR' as AppLocale },
])

const langLabel = computed(() => {
  if (locale.value === 'en-US') return 'EN'
  if (locale.value === 'ko-KR') return '한'
  return '中'
})

const userName = computed(() => {
  if (!auth.userInfo?.full_name) return ''
  return auth.userInfo.full_name
})

function onLogout() {
  auth.logout()
  const code = getStoredTenantCode()
  router.replace(code ? `/t/${code}/login` : '/login')
}

function goNotifications() {
  router.push({ name: 'notifications' })
}

function onSelectLang(action: { name: string; value?: AppLocale }) {
  if (!action.value || action.value === locale.value) {
    showLangSheet.value = false
    return
  }
  setStoredLocale(action.value)
  locale.value = action.value
  applyVantLocale(action.value)
  showLangSheet.value = false
  window.location.reload()
}

onMounted(async () => {
  if (!auth.userInfo) {
    await auth.fetchMe()
  }
  auth.refreshUnreadNotificationCount()
})

watch(
  () => route.fullPath,
  () => {
    auth.refreshUnreadNotificationCount()
  },
)
</script>

<template>
  <div class="pc-wrapper min-h-dvh bg-zinc-100">
    <div class="app-shell">
      <van-nav-bar :title="title" fixed placeholder>
        <template #right>
          <div class="flex max-w-[60vw] items-center gap-1">
            <van-button size="mini" type="primary" plain @click="showLangSheet = true">{{ langLabel }}</van-button>
            <span
              class="max-w-[4rem] cursor-pointer truncate text-xs text-zinc-500"
              @click="router.push({ name: 'profile' })"
            >{{ userName || t('layout.profile') }}</span>
            <van-badge
              v-if="auth.hasPermission('notification.view')"
              :content="auth.unreadNotificationCount"
              :show-zero="false"
            >
              <button
                type="button"
                class="flex h-8 w-8 items-center justify-center rounded-md border-0 bg-transparent p-0 text-[var(--van-primary-color)]"
                :aria-label="t('layout.notifications')"
                @click="goNotifications"
              >
                <van-icon name="bell" size="18" />
              </button>
            </van-badge>
            <van-button size="mini" type="primary" plain @click="onLogout">{{ t('layout.logout') }}</van-button>
          </div>
        </template>
      </van-nav-bar>

      <div class="px-3 py-3 pb-16">
        <router-view />
      </div>

      <!-- 员工底部 Tab -->
      <van-tabbar v-if="auth.isEmployee" route fixed placeholder>
        <van-tabbar-item replace :to="{ name: 'home' }" icon="home-o">{{ t('nav.home') }}</van-tabbar-item>
        <van-tabbar-item replace :to="{ name: 'tasks' }" icon="todo-list-o">{{ t('nav.tasks') }}</van-tabbar-item>
        <van-tabbar-item replace :to="{ name: 'report' }" icon="scan">{{ t('nav.report') }}</van-tabbar-item>
        <van-tabbar-item replace :to="{ name: 'attendance' }" icon="clock-o">{{ t('nav.attendance') }}</van-tabbar-item>
        <van-tabbar-item replace :to="{ name: 'wages' }" icon="balance-o">{{ t('nav.wages') }}</van-tabbar-item>
      </van-tabbar>

      <!-- 客户底部 Tab -->
      <van-tabbar v-else-if="auth.isCustomer" route fixed placeholder>
        <van-tabbar-item replace :to="{ name: 'customerOrder' }" icon="home-o">{{ t('customer.nav.home') }}</van-tabbar-item>
        <van-tabbar-item replace :to="{ name: 'customerOrder' }" icon="shopping-cart-o">{{ t('customer.nav.order') }}</van-tabbar-item>
        <van-tabbar-item replace :to="{ name: 'customerStatements' }" icon="bill-o">{{ t('customer.nav.statements') }}</van-tabbar-item>
      </van-tabbar>

      <!-- 默认底部 Tab -->
      <van-tabbar v-else route fixed placeholder>
        <van-tabbar-item replace :to="{ name: 'home' }" icon="home-o">{{ t('nav.home') }}</van-tabbar-item>
        <van-tabbar-item replace :to="{ name: 'tasks' }" icon="todo-list-o">{{ t('nav.tasks') }}</van-tabbar-item>
        <van-tabbar-item replace :to="{ name: 'report' }" icon="scan">{{ t('nav.report') }}</van-tabbar-item>
      </van-tabbar>

      <van-action-sheet
        v-model:show="showLangSheet"
        :actions="langActions"
        :cancel-text="t('common.cancel')"
        :description="t('common.language')"
        close-on-click-action
        @select="onSelectLang"
      />
    </div>
  </div>
</template>

<style scoped>
/* PC 端适配：限制宽度居中显示，模拟手机效果 */
@media (min-width: 768px) {
  .pc-wrapper {
    display: flex;
    justify-content: center;
    align-items: flex-start;
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    min-height: 100vh;
    padding: 20px 0;
  }
  .app-shell {
    width: 100%;
    max-width: 430px;
    min-height: calc(100vh - 40px);
    background: #f4f4f5;
    border-radius: 24px;
    box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
    overflow: hidden;
    position: relative;
  }
  .app-shell :deep(.van-nav-bar) {
    border-radius: 24px 24px 0 0;
  }
  .app-shell :deep(.van-tabbar) {
    border-radius: 0 0 24px 24px;
  }
}
</style>
