<template>
  <el-container class="h-screen w-screen bg-[var(--admin-page-bg)]">
    <el-aside
      v-show="!isNarrow"
      :width="collapsed ? 'var(--admin-sider-collapsed-width)' : 'var(--admin-sider-width)'"
      class="admin-sider shrink-0 flex flex-col border-r border-[var(--admin-sider-border)] bg-[var(--admin-sider-bg)] transition-[width] duration-200"
      :class="{ 'admin-sider--collapsed': collapsed }"
    >
      <div
        class="admin-sider__brand h-14 px-4 flex items-center gap-3 shrink-0 border-b border-[var(--admin-sider-border)]"
      >
        <AdminBrand :compact="collapsed" />
      </div>
      <div class="flex-1 min-h-0 py-2 overflow-hidden flex flex-col">
        <AppMenu :collapse="collapsed" />
      </div>
    </el-aside>
    <el-container class="min-w-0 min-h-0 flex flex-col">
      <el-header
        height="52px"
        class="admin-header flex items-center justify-between gap-3 px-3 sm:px-5 shrink-0 bg-[var(--admin-header-bg)] border-b border-[var(--admin-sider-border)]"
      >
        <div class="flex items-center gap-2 min-w-0 flex-1">
          <el-button
            v-if="isNarrow"
            type="primary"
            link
            class="shrink-0 !px-1"
            :aria-label="t('layout.openMenu')"
            @click="drawerOpen = true"
          >
            <el-icon :size="22"><MenuIcon /></el-icon>
          </el-button>
          <el-button
            v-else
            type="primary"
            link
            class="shrink-0 !px-1 hidden sm:inline-flex"
            :aria-label="t('layout.collapseSidebar')"
            @click="toggleCollapse"
          >
            <el-icon :size="20"><Fold v-if="!collapsed" /><Expand v-else /></el-icon>
          </el-button>
          <div class="min-w-0 flex-1">
            <el-breadcrumb :separator-icon="ArrowRight" class="admin-breadcrumb hidden sm:flex sm:items-center flex-wrap">
              <el-breadcrumb-item :to="{ path: '/home' }">{{ t('common.home') }}</el-breadcrumb-item>
              <el-breadcrumb-item v-for="(seg, idx) in breadcrumbSegments" :key="seg.name">
                <router-link v-if="idx < breadcrumbSegments.length - 1" :to="{ name: seg.name }">
                  {{ seg.title }}
                </router-link>
                <span v-else class="breadcrumb-current">{{ seg.title }}</span>
              </el-breadcrumb-item>
            </el-breadcrumb>
            <div class="text-[13px] text-[var(--admin-brand-subtitle)] font-medium truncate sm:hidden">
              {{ currentTitle }}
            </div>
          </div>
        </div>
        <div class="flex items-center gap-1 sm:gap-2 shrink-0">
          <el-tooltip :content="isDark ? t('common.lightMode') : t('common.darkMode')" placement="bottom">
            <el-button type="primary" link class="!px-2" :aria-label="t('layout.toggleTheme')" @click="toggleTheme">
              <el-icon :size="18"><Sunny v-if="isDark" /><Moon v-else /></el-icon>
            </el-button>
          </el-tooltip>
          <div
            class="hidden md:flex items-center gap-2 px-2 py-1 rounded-lg bg-[var(--el-fill-color-light)] max-w-[220px] border border-[var(--el-border-color-light)] cursor-pointer hover:opacity-90 transition-opacity"
            role="button"
            tabindex="0"
            @click="goProfile"
            @keydown.enter="goProfile"
          >
            <div
              class="w-7 h-7 rounded-md text-xs font-semibold flex items-center justify-center shrink-0"
              style="color: var(--admin-brand-mark-text); background: var(--admin-brand-mark-bg)"
            >
              {{ userInitial }}
            </div>
            <span class="text-[13px] text-[var(--el-text-color-regular)] truncate">{{ userLabel }}</span>
          </div>
          <el-button v-if="isNarrow" size="small" plain @click="goProfile">{{ t('layout.personalCenter') }}</el-button>
          <el-button size="small" plain @click="onLogout">{{ t('layout.logout') }}</el-button>
        </div>
      </el-header>
      <el-main class="admin-main !p-3 sm:!p-5 min-h-0 overflow-y-auto">
        <div class="max-w-[1480px] mx-auto w-full min-w-0">
          <router-view />
        </div>
      </el-main>
    </el-container>

    <el-drawer v-model="drawerOpen" direction="ltr" size="260px" :with-header="false" append-to-body class="admin-nav-drawer">
      <div class="admin-sider__brand h-14 px-4 flex items-center gap-3 border-b border-[var(--admin-sider-border)] bg-[var(--admin-sider-bg)]">
        <AdminBrand />
      </div>
      <div class="py-2 overflow-y-auto bg-[var(--admin-sider-bg)]" style="max-height: calc(100vh - 3.5rem)">
        <AppMenu layout="drawer" />
      </div>
    </el-drawer>
  </el-container>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import {
  ArrowRight,
  Expand,
  Fold,
  Menu as MenuIcon,
  Moon,
  Sunny,
} from '@element-plus/icons-vue'
import AdminBrand from '@/components/AdminBrand.vue'
import { useAdminTheme } from '@/composables/useAdminTheme'
import { useSidebarCollapse } from '@/composables/useSidebarCollapse'
import { useAuthStore } from '@/stores/auth'
import AppMenu from '@/layouts/AppMenu.vue'

const NARROW_QUERY = '(max-width: 1023px)'

const { t, locale } = useI18n()

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const { toggleTheme, isDark } = useAdminTheme()
const { collapsed, toggleCollapse } = useSidebarCollapse()

const isNarrow = ref(false)
const drawerOpen = ref(false)
let mq: MediaQueryList | null = null

function syncNarrow() {
  const narrow = mq?.matches ?? false
  isNarrow.value = narrow
  if (!narrow) drawerOpen.value = false
}

function resolveRouteTitle(title: unknown): string {
  if (typeof title === 'function') return title()
  if (typeof title === 'string') return title
  return ''
}

const currentTitle = computed(() => resolveRouteTitle(route.meta.title))

const breadcrumbSegments = computed(() =>
  route.matched
    .filter((r) => r.meta?.title && r.name && !r.redirect)
    .map((r) => ({
      title: resolveRouteTitle(r.meta.title),
      name: r.name as string,
    }))
)

const userLabel = computed(() => {
  const me = auth.me
  if (!me) return ''
  return me.full_name ? `${me.full_name}（${me.username}）` : me.username
})

const userInitial = computed(() => {
  const me = auth.me
  if (!me) return '?'
  const base = me.full_name?.trim() || me.username?.trim() || '?'
  return base.slice(0, 1).toUpperCase()
})

function goProfile() {
  router.push('/account/profile')
}

function onLogout() {
  auth.logout()
  router.replace('/login')
}

onMounted(() => {
  mq = window.matchMedia(NARROW_QUERY)
  syncNarrow()
  mq.addEventListener('change', syncNarrow)
})

onUnmounted(() => {
  mq?.removeEventListener('change', syncNarrow)
})

watch(
  () => route.path,
  () => {
    if (isNarrow.value) drawerOpen.value = false
  }
)
</script>

<style scoped>
.admin-main {
  background: var(--admin-page-bg);
}
</style>
