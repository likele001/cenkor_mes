<template>
  <div class="min-h-screen bg-gray-50 p-6">
    <!-- 顶部标题与操作 -->
    <div class="mb-6 flex flex-wrap items-center justify-between gap-3">
      <div>
        <h1 class="text-2xl font-bold text-gray-900">功能市场</h1>
        <p class="mt-1 text-sm text-gray-500">连接 Cenkor 门户，浏览并一键安装扩展功能（即时生效，无需重启）</p>
      </div>
      <div class="flex items-center gap-3">
        <el-tag v-if="status.bound" type="success" size="large">
          已连接：{{ status.account || '门户账号' }}
        </el-tag>
        <el-tag v-else type="info" size="large">未连接门户</el-tag>
        <el-button v-if="status.bound" @click="showConnect = true">门户设置</el-button>
        <el-button v-else type="primary" @click="showConnect = true">
          <el-icon class="mr-1"><Link /></el-icon>
          连接门户
        </el-button>
        <el-button v-if="status.bound" type="primary" :loading="loading" @click="fetchApps">
          <el-icon class="mr-1"><Refresh /></el-icon>
          刷新
        </el-button>
      </div>
    </div>

    <!-- 未连接提示 -->
    <el-alert
      v-if="!status.bound"
      title="尚未连接 Cenkor 门户"
      description="连接后可浏览市场、购买并一键安装扩展。整个过程无需手工运维。"
      type="warning"
      show-icon
      :closable="false"
      class="mb-6"
    >
      <template #default>
        <el-button type="primary" class="mt-2" @click="showConnect = true">立即连接门户</el-button>
      </template>
    </el-alert>

    <!-- 应用列表 -->
    <div
      v-if="status.bound && apps.length > 0"
      class="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4"
    >
      <div
        v-for="app in apps"
        :key="app.key"
        class="group relative overflow-hidden rounded-xl border border-gray-200 bg-white p-5 shadow-sm transition-all hover:shadow-md"
      >
        <div class="mb-3 flex items-start gap-3">
          <div class="flex h-12 w-12 shrink-0 items-center justify-center rounded-lg bg-gradient-to-br from-blue-500 to-indigo-600 text-xl font-bold text-white">
            {{ app.icon || app.name.charAt(0).toUpperCase() }}
          </div>
          <div class="min-w-0 flex-1">
            <h3 class="truncate text-base font-semibold text-gray-900">{{ app.name }}</h3>
            <p class="text-xs text-gray-500">{{ app.key }}</p>
          </div>
        </div>

        <p class="mb-4 line-clamp-2 text-sm text-gray-600">{{ app.description || '暂无描述' }}</p>

        <div class="mb-4 flex flex-wrap gap-2">
          <el-tag v-if="app.installed" type="success" size="small">已安装 {{ app.installed_version }}</el-tag>
          <el-tag v-else type="info" size="small">未安装</el-tag>

          <el-tag v-if="app.licensed" type="success" size="small">已持有授权</el-tag>
          <el-tag v-else type="warning" size="small">{{ app.price ? '需购买' : '需领取' }}</el-tag>

          <el-tag v-if="app.category" size="small">{{ app.category }}</el-tag>

          <el-tag v-if="app.license_expires_at" type="info" size="small">
            到期 {{ formatDate(app.license_expires_at) }}
          </el-tag>
        </div>

        <div class="flex flex-wrap gap-2">
          <el-button
            v-if="!app.installed"
            type="primary"
            size="small"
            class="flex-1"
            :disabled="!app.licensed"
            :loading="installingKey === app.key"
            @click="handleInstall(app)"
          >
            {{ app.licensed ? '安装' : '未持有授权' }}
          </el-button>
          <template v-else>
            <el-button
              v-if="hasUpdate(app)"
              type="warning"
              size="small"
              class="flex-1"
              :loading="installingKey === app.key"
              @click="handleInstall(app)"
            >
              更新到 {{ app.latest_version }}
            </el-button>
            <el-button v-else type="success" size="small" class="flex-1" disabled>
              已安装 {{ app.installed_version }}
            </el-button>
            <el-button
              type="danger"
              size="small"
              plain
              :loading="uninstallingKey === app.key"
              @click="handleUninstall(app)"
            >
              卸载
            </el-button>
          </template>
          <el-button v-if="!app.licensed" size="small" plain @click="openPortal">
            前往门户
          </el-button>
        </div>

        <div v-if="app.latest_version" class="mt-3 text-xs text-gray-400">最新版本: {{ app.latest_version }}</div>
      </div>
    </div>

    <el-empty v-else-if="!loading && status.bound" description="暂无可用应用，请前往门户浏览购买" />

    <div v-if="loading" class="flex items-center justify-center py-20">
      <el-icon class="is-loading mr-2 text-2xl"><Loading /></el-icon>
      <span class="text-gray-500">加载中...</span>
    </div>

    <!-- 门户连接向导 -->
    <el-dialog v-model="showConnect" title="连接 Cenkor 门户" width="560px" :close-on-click-modal="false" @closed="onDialogClosed">
      <!-- 步骤 1：hub 地址 -->
      <div class="mb-5">
        <div class="mb-2 flex items-center gap-2">
          <el-tag size="small" :type="status.hub_url ? 'success' : 'warning'">1</el-tag>
          <span class="font-medium text-gray-800">门户地址</span>
        </div>
        <div class="flex gap-2">
          <el-input v-model="hubUrl" placeholder="https://admin.cenkor.cn" clearable @keyup.enter="saveHub" />
          <el-button type="primary" :loading="savingHub" @click="saveHub">保存</el-button>
        </div>
        <p class="mt-1 text-xs text-gray-400">填写 Cenkor 门户 hub 地址（如 https://admin.cenkor.cn），保存后即可发起绑定。</p>
      </div>

      <!-- 步骤 2：设备码绑定 -->
      <div>
        <div class="mb-2 flex items-center gap-2">
          <el-tag size="small" :type="status.bound ? 'success' : (bind.active ? 'warning' : 'info')">2</el-tag>
          <span class="font-medium text-gray-800">绑定门户账号</span>
          <el-tag v-if="status.bound" type="success" size="small" class="ml-2">已连接</el-tag>
        </div>

        <!-- 已绑定：展示账号 + 解绑 -->
        <div v-if="status.bound" class="rounded-lg border border-green-200 bg-green-50 p-4">
          <p class="text-sm text-gray-700">
            本实例已绑定门户账号：<span class="font-medium">{{ status.account || '-' }}</span>
          </p>
          <el-button type="danger" plain size="small" class="mt-3" :loading="unbinding" @click="handleUnbind">
            解绑本实例
          </el-button>
        </div>

        <!-- 未绑定 -->
        <div v-else>
          <!-- 未发起：按钮 -->
          <div v-if="!bind.active">
            <el-button
              type="primary"
              :disabled="!status.hub_url"
              :loading="startingBind"
              @click="startBind"
            >
              发起连接
            </el-button>
            <p v-if="!status.hub_url" class="mt-2 text-xs text-gray-400">请先保存门户地址（步骤 1）。</p>
          </div>

          <!-- 已发起：展示绑定码，等待门户确认 -->
          <div v-else class="rounded-lg border border-blue-200 bg-blue-50 p-4">
            <p class="text-sm text-gray-700">请打开门户页面并登录，输入以下一次性绑定码完成连接：</p>
            <div class="my-3 flex items-center justify-center gap-3">
              <span class="font-mono text-3xl font-bold tracking-widest text-blue-700">{{ bind.user_code }}</span>
              <el-button size="small" text @click="copyCode">复制</el-button>
            </div>
            <div class="text-center">
              <el-link type="primary" :href="bind.verification_uri" target="_blank">
                打开门户确认页 →
              </el-link>
              <span class="ml-3 text-xs text-gray-400">{{ bind.countdown > 0 ? `${bind.countdown}s 后过期` : '已过期' }}</span>
            </div>
            <div class="mt-4 flex items-center justify-center gap-2">
              <el-icon v-if="polling" class="is-loading text-blue-500"><Loading /></el-icon>
              <span class="text-sm text-gray-600">
                {{ polling ? '等待门户确认…' : '轮询已停止' }}
              </span>
            </div>
            <div class="mt-3 text-center">
              <el-button size="small" @click="cancelBind">取消</el-button>
            </div>
          </div>
        </div>
      </div>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted, onBeforeUnmount } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Link, Refresh, Loading } from '@element-plus/icons-vue'
import {
  getMarketStatus,
  saveMarketHub,
  bindStart,
  bindPoll,
  bindCancel,
  bindUnbind,
  getMarketApps,
  installMarketApp,
  uninstallMarketApp,
  type MarketApp,
  type MarketStatus,
} from '@/api/market'
import { reloadExtensions } from '@/utils/extensionLoader'

const loading = ref(false)
const apps = ref<MarketApp[]>([])
const status = reactive<MarketStatus>({ hub_url: '', product: '', bound: false, account: '', instance_uid: '' })

const installingKey = ref('')
const uninstallingKey = ref('')

// 连接向导
const showConnect = ref(false)
const hubUrl = ref('')
const savingHub = ref(false)
const startingBind = ref(false)
const unbinding = ref(false)
const polling = ref(false)

const bind = reactive({
  active: false,
  user_code: '',
  verification_uri: '',
  countdown: 0,
})

let pollTimer: ReturnType<typeof setInterval> | null = null
let countdownTimer: ReturnType<typeof setInterval> | null = null

function clearTimers() {
  if (pollTimer) {
    clearInterval(pollTimer)
    pollTimer = null
  }
  if (countdownTimer) {
    clearInterval(countdownTimer)
    countdownTimer = null
  }
  polling.value = false
}

function formatDate(s: string | null): string {
  if (!s) return ''
  const d = new Date(s)
  return isNaN(d.getTime()) ? s : d.toLocaleDateString()
}

function hasUpdate(app: MarketApp): boolean {
  return app.installed && !!app.latest_version && app.latest_version !== app.installed_version
}

function openPortal() {
  const url = status.hub_url || 'https://admin.cenkor.cn'
  window.open(url, '_blank')
}

async function fetchStatus() {
  try {
    const res = await getMarketStatus()
    Object.assign(status, res)
    hubUrl.value = res.hub_url
  } catch (e) {
    console.error('fetchStatus error:', e)
  }
}

async function fetchApps() {
  loading.value = true
  try {
    const res = await getMarketApps()
    apps.value = res.items
    status.bound = res.bound
    status.account = res.account
    status.hub_url = res.hub_url
  } catch (e) {
    console.error('fetchApps error:', e)
  } finally {
    loading.value = false
  }
}

async function saveHub() {
  const url = hubUrl.value.trim().replace(/\/+$/, '')
  if (!url) {
    ElMessage.warning('请填写门户地址')
    return
  }
  savingHub.value = true
  try {
    await saveMarketHub(url)
    status.hub_url = url
    ElMessage.success('门户地址已保存')
  } catch (e) {
    console.error('saveHub error:', e)
  } finally {
    savingHub.value = false
  }
}

async function startBind() {
  startingBind.value = true
  try {
    const res = await bindStart()
    bind.active = true
    bind.user_code = res.user_code
    bind.verification_uri = res.verification_uri_complete || res.verification_uri
    bind.countdown = res.expires_in || 600
    startPolling(Math.max(2, res.interval || 5))
    startCountdown()
  } catch (e) {
    console.error('startBind error:', e)
  } finally {
    startingBind.value = false
  }
}

function startPolling(intervalSec: number) {
  clearTimers()
  polling.value = true
  pollTimer = setInterval(pollOnce, intervalSec * 1000)
}

function startCountdown() {
  if (countdownTimer) clearInterval(countdownTimer)
  countdownTimer = setInterval(() => {
    if (bind.countdown > 0) bind.countdown -= 1
    else stopBindWaiting()
  }, 1000)
}

async function pollOnce() {
  try {
    const res = await bindPoll()
    if (res.status === 'approved') {
      stopBindWaiting()
      bind.active = false
      await fetchStatus()
      await fetchApps()
      await reloadExtensions()
      ElMessage.success('已连接门户账号：' + (status.account || ''))
    } else if (['expired', 'denied', 'consumed'].includes(res.status)) {
      stopBindWaiting()
      bind.active = false
      ElMessage.warning('绑定码已失效，请重新发起连接')
    }
  } catch (e) {
    console.error('pollOnce error:', e)
  }
}

function stopBindWaiting() {
  clearTimers()
}

async function cancelBind() {
  try {
    await bindCancel()
  } catch (e) {
    console.error('cancelBind error:', e)
  }
  stopBindWaiting()
  bind.active = false
  bind.user_code = ''
  bind.countdown = 0
}

async function handleUnbind() {
  try {
    await ElMessageBox.confirm('解绑后将无法从门户拉取已购授权，确定解绑本实例？', '确认解绑', {
      confirmButtonText: '确定解绑',
      cancelButtonText: '取消',
      type: 'warning',
    })
  } catch {
    return
  }
  unbinding.value = true
  try {
    await bindUnbind()
    await fetchStatus()
    apps.value = []
    ElMessage.success('已解绑')
  } catch (e) {
    console.error('unbind error:', e)
  } finally {
    unbinding.value = false
  }
}

async function copyCode() {
  try {
    await navigator.clipboard.writeText(bind.user_code)
    ElMessage.success('绑定码已复制')
  } catch {
    ElMessage.warning('复制失败，请手动输入')
  }
}

function onDialogClosed() {
  // 关闭弹窗时若仍在等待绑定但尚未成功，保留轮询；若已取消则清理
  if (!status.bound && !bind.active) clearTimers()
}

async function handleInstall(app: MarketApp) {
  try {
    await ElMessageBox.confirm(
      `确定要安装「${app.name}」吗？安装后即时生效，无需重启。`,
      '确认安装',
      { confirmButtonText: '确定', cancelButtonText: '取消', type: 'info' },
    )
  } catch {
    return
  }
  installingKey.value = app.key
  try {
    const res = await installMarketApp(app.key)
    await fetchApps()
    await reloadExtensions()
    ElMessage.success(res.message || '安装成功，已即时生效')
  } catch (e) {
    console.error('install error:', e)
  } finally {
    installingKey.value = ''
  }
}

async function handleUninstall(app: MarketApp) {
  try {
    await ElMessageBox.confirm(
      `确定要卸载「${app.name}」吗？卸载将删除该扩展文件并即时生效。`,
      '确认卸载',
      { confirmButtonText: '确定卸载', cancelButtonText: '取消', type: 'warning' },
    )
  } catch {
    return
  }
  uninstallingKey.value = app.key
  try {
    const res = await uninstallMarketApp(app.key)
    await fetchApps()
    await reloadExtensions()
    ElMessage.success(res.message || '卸载成功，已即时生效')
  } catch (e) {
    console.error('uninstall error:', e)
  } finally {
    uninstallingKey.value = ''
  }
}

onMounted(async () => {
  await fetchStatus()
  if (status.bound) await fetchApps()
})

onBeforeUnmount(() => clearTimers())
</script>

<style scoped>
.line-clamp-2 {
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
</style>
