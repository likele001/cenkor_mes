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

    <!-- 已购概况：数字来自实例本地的授权快照，不是实时查 hub（见 fetchStatus 注释） -->
    <div v-if="status.bound" class="mb-6">
      <div class="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <div class="rounded-lg border border-gray-200 bg-white p-4">
          <div class="text-xs text-gray-500">已购扩展</div>
          <div class="mt-1 text-2xl font-bold text-gray-900">{{ status.purchased_count ?? 0 }}</div>
        </div>
        <div class="rounded-lg border border-gray-200 bg-white p-4">
          <div class="text-xs text-gray-500">可更新</div>
          <div
            class="mt-1 text-2xl font-bold"
            :class="(status.updatable_count ?? 0) > 0 ? 'text-blue-600' : 'text-gray-900'"
          >
            {{ status.updatable_count ?? 0 }}
          </div>
        </div>
        <div class="rounded-lg border border-gray-200 bg-white p-4">
          <div class="text-xs text-gray-500">最近到期</div>
          <div class="mt-1 text-2xl font-bold" :class="expirySoon ? 'text-red-600' : 'text-gray-900'">
            {{ expiryText }}
          </div>
        </div>
      </div>
      <p class="mt-2 text-xs text-gray-400">
        <span v-if="status.hub_reachable === false">门户最近一次同步未成功，以下为上次快照的数据。</span>
        <span v-else-if="status.hub_reachable === null && !status.snapshot_synced_at">
          首次同步后显示，打开本页或点上方刷新即可触发。
        </span>
        <span v-else-if="status.snapshot_synced_at">统计截至 {{ snapshotText }}。</span>
      </p>
    </div>

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

          <el-tag v-if="app.installed && app.health === 'ok'" type="success" size="small" effect="plain">
            健康
          </el-tag>
          <el-tag v-else-if="app.installed && app.health" type="danger" size="small" effect="plain">
            异常
          </el-tag>
          <el-tag v-if="app.installed && app.status === 'installed_disabled'" type="info" size="small">
            已禁用
          </el-tag>
          <el-tag v-if="app.installed && app.status === 'rollback_blocked'" type="warning" size="small">
            回滚受阻
          </el-tag>
          <el-tag v-if="app.worker_restart_required" type="warning" size="small" effect="plain">
            任务需重启 worker
          </el-tag>
          <el-tag v-if="app.multi_worker" type="warning" size="small" effect="plain">
            多 worker：需全部重启
          </el-tag>
          <el-tag v-if="app.installed && app.data_policy === 'keep'" size="small" effect="plain">
            卸载保留数据
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
            <el-button
              v-if="app.enabled"
              size="small"
              plain
              :loading="lifecycleKey === app.key"
              @click="handleDisable(app)"
            >
              禁用
            </el-button>
            <el-button
              v-else
              type="primary"
              size="small"
              plain
              :loading="lifecycleKey === app.key"
              @click="handleEnable(app)"
            >
              启用
            </el-button>
            <el-button
              v-if="app.has_backup"
              size="small"
              plain
              :loading="lifecycleKey === app.key"
              @click="handleRollback(app)"
            >
              回滚
            </el-button>
            <el-button
              size="small"
              plain
              :loading="lifecycleKey === app.key"
              @click="handleRepair(app)"
            >
              修复
            </el-button>
          </template>
          <el-button v-if="!app.licensed" size="small" plain @click="openPortal(app.key)">
            前往门户
          </el-button>
        </div>

        <div v-if="app.latest_version" class="mt-3 text-xs text-gray-400">
          最新版本: {{ app.latest_version }}
          <span v-if="app.previous_version">· 上一版 {{ app.previous_version }}</span>
          <span v-if="app.last_operation">· 上次操作 {{ app.last_operation }}</span>
        </div>
        <div v-if="app.last_error" class="mt-1 line-clamp-2 text-xs text-red-500">{{ app.last_error }}</div>
      </div>
    </div>

    <el-empty v-else-if="!loading && status.bound" description="暂无可用应用，请前往门户浏览购买">
      <el-button type="primary" plain @click="openPortal()">前往门户浏览</el-button>
    </el-empty>

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
          <el-input v-model="hubUrl" placeholder="https://portal.cenkor.cn" clearable @keyup.enter="saveHub" />
          <el-button type="primary" :loading="savingHub" @click="saveHub">保存</el-button>
        </div>
        <p class="mt-1 text-xs text-gray-400">填写 Cenkor 门户地址（如 https://portal.cenkor.cn，它与后台 API 同源），保存后即可发起绑定。</p>
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
import { ref, reactive, computed, onMounted, onBeforeUnmount } from 'vue'
import { useRouter } from 'vue-router'
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
  enableMarketApp,
  disableMarketApp,
  rollbackMarketApp,
  repairMarketApp,
  type MarketApp,
  type MarketStatus,
} from '@/api/market'
import { reloadExtensions, isExtensionRouteActive } from '@/utils/extensionLoader'
import { useAuthStore } from '@/stores/auth'

const loading = ref(false)
const apps = ref<MarketApp[]>([])
const status = reactive<MarketStatus>({
  hub_url: '',
  product: '',
  bound: false,
  account: '',
  instance_uid: '',
  hub_reachable: null,
  purchased_count: 0,
  updatable_count: 0,
  nearest_expiry: null,
  snapshot_synced_at: '',
})

// 概况数字口径：后端只读进程内授权快照，缺值按 0/「无」显示，不做乐观推断。
function _date(raw?: string | null): Date | null {
  if (!raw) return null
  const d = new Date(raw)
  return Number.isNaN(d.getTime()) ? null : d
}
const expiryDate = computed(() => _date(status.nearest_expiry))
const expiryText = computed(() => {
  const d = expiryDate.value
  if (!d) return status.nearest_expiry ? String(status.nearest_expiry) : '无（均为买断）'
  return d.toLocaleDateString('zh-CN')
})
// 30 天内到期标红：与列表里「到期 {d}」的提醒口径一致
const expirySoon = computed(() => {
  const d = expiryDate.value
  return !!d && d.getTime() - Date.now() < 30 * 86400000
})
const snapshotText = computed(() => {
  const d = _date(status.snapshot_synced_at)
  return d ? d.toLocaleString('zh-CN') : String(status.snapshot_synced_at || '')
})

const installingKey = ref('')
const uninstallingKey = ref('')
const lifecycleKey = ref('')
const router = useRouter()
const auth = useAuthStore()

/**
 * 生命周期动作统一收尾：权限缓存 → 前端插件 → 市场列表。
 *
 * 顺序不能反：先 fetchMe 才能让新装扩展的权限进入当前用户缓存（否则菜单被
 * hasAnyPermission 过滤掉），再 reloadExtensions 注入动态路由/菜单，最后刷新列表。
 */
async function refreshAfterLifecycle(key?: string) {
  try {
    await auth.fetchMe()
  } catch (e) {
    console.warn('[market] 刷新当前用户权限失败', e)
  }
  const result = await reloadExtensions()
  await fetchApps()
  if (result.failed.length) {
    ElMessage.warning(`以下扩展前端加载失败，可尝试刷新页面：${result.failed.join('、')}`)
  }
  if (key && !runtimeStillActive(key) && isExtensionRouteActive(key)) {
    await router.replace('/market')
  }
}

/** 卸载/禁用后，该扩展是否仍处于可访问状态（有前端注册即视为仍可停留） */
function runtimeStillActive(key: string): boolean {
  const app = apps.value.find((x) => x.key === key)
  return Boolean(app?.installed && app?.enabled)
}

/** 操作后统一提示：worker 重启/多 worker 不假装热生效 */
function notifyWorker(app: MarketApp, message: string) {
  if (app.worker_restart_required) {
    ElMessage.warning(`${message}；后台 Celery 任务需重启 worker 后生效`)
  } else {
    ElMessage.success(message)
  }
}

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

/** 弹窗里的 changelog 来自 hub/开发者，落 HTML 前必须转义，避免被当成标签执行 */
function escapeHtml(s: string): string {
  const map: Record<string, string> = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }
  return String(s || '').replace(/[&<>"']/g, (c) => map[c] || c)
}

function verCmp(a: string, b: string): number {
  const pa = String(a || '').split('.').map((x) => parseInt(x, 10) || 0)
  const pb = String(b || '').split('.').map((x) => parseInt(x, 10) || 0)
  const n = Math.max(pa.length, pb.length)
  for (let i = 0; i < n; i++) {
    const d = (pa[i] || 0) - (pb[i] || 0)
    if (d) return d > 0 ? 1 : -1
  }
  return 0
}

function hasUpdate(app: MarketApp): boolean {
  // 只有 hub 发布版本 > 本地已装版本才算可更新：按字符串比会把降级（1.10 → 1.9）也催成升级
  return app.installed && !!app.latest_version && !!app.installed_version
    && verCmp(app.latest_version, app.installed_version) > 0
}

function openPortal(appKey?: string) {
  // hub 地址即门户同源（portal.cenkor.cn 反代了 /api/v1/store）；
  // “前往门户”应打开门户应用中心，而非后台 API 根地址。
  const base = (status.hub_url || 'https://portal.cenkor.cn').replace(/\/+$/, '')
  const url = appKey ? `${base}/apps/${appKey}` : `${base}/apps`
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
    // /apps 在后端会顺手刷新授权快照，所以紧接着再取一次概况：
    // 点「刷新」后数字与列表同源，不会出现列表已更新、卡片还是旧数。
    await fetchStatus()
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
      await refreshAfterLifecycle()
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
  // 已装 → 更新：展示 changelog / min_core_version / 数据策略 / 备份提示；
  // 未装 → 安装：只做一次确认。两条分支都走 POST /admin/market/install。
  const updating = hasUpdate(app)
  const html: string[] = []
  if (updating) {
    html.push(
      `<p><b>${escapeHtml(app.name)}</b>：${escapeHtml(app.installed_version)} → ${escapeHtml(app.latest_version)}</p>`,
      `<p style="margin-top:8px"><span style="color:#6b7280">更新内容：</span>${
        app.changelog ? escapeHtml(app.changelog) : '（本版未填写 changelog）'
      }</p>`,
      `<p><span style="color:#6b7280">最低宿主版本：</span>${escapeHtml(app.min_core_version || '未声明')}</p>`,
      `<p><span style="color:#6b7280">数据策略：</span>${
        app.data_policy === 'keep' || !app.data_policy ? '保留（默认，表与文件不动）' : escapeHtml(app.data_policy)
      }</p>`,
      `<p style="margin-top:8px;color:#92400e">旧版会先备份到 extensions/.backup；迁移或健康检查失败会自动回滚上一版。</p>`,
    )
  } else {
    html.push(`<p>确定要安装「${escapeHtml(app.name)}」吗？安装后即时生效，无需重启。</p>`)
  }
  try {
    await ElMessageBox.confirm(html.join(''), updating ? '确认更新' : '确认安装', {
      confirmButtonText: updating ? '确定更新' : '确定',
      cancelButtonText: '取消',
      type: 'info',
      dangerouslyUseHTMLString: true,
    })
  } catch {
    return
  }
  installingKey.value = app.key
  try {
    const res = await installMarketApp(app.key)
    await refreshAfterLifecycle(app.key)
    notifyWorker(app, res.message || '安装成功，已即时生效')
  } catch (e) {
    console.error('install error:', e)
  } finally {
    installingKey.value = ''
  }
}

async function handleUninstall(app: MarketApp) {
  // 二选一：保留数据（默认，可重装恢复）/ 彻底清除（不可逆，要求输入 key）
  let action = 'keep'
  let confirmKey = ''
  try {
    await ElMessageBox.confirm(
      `卸载「${app.name}」后默认保留数据表与文件，重装即可恢复。\n如需彻底清除（删除应用自有数据表与文件，不可恢复），请选择「彻底清除」。`,
      '确认卸载',
      {
        confirmButtonText: '保留数据并卸载',
        cancelButtonText: '彻底清除…',
        distinguishCancelAndClose: true,
        type: 'warning',
      },
    )
  } catch (actionName) {
    if (actionName !== 'cancel') return
    try {
      const input = await ElMessageBox.prompt(
        `彻底清除会删除「${app.key}」自有的数据表与文件（先自动导出 JSONL 备份），不可恢复。\n请输入扩展 key 以确认：`,
        '彻底清除（不可逆）',
        {
          confirmButtonText: '确认彻底清除',
          cancelButtonText: '取消',
          inputValidator: (v: string) => (v === app.key ? true : `请输入 ${app.key}`),
        },
      )
      action = 'purge'
      confirmKey = input.value
    } catch {
      return
    }
  }
  uninstallingKey.value = app.key
  try {
    const res = await uninstallMarketApp(app.key, { purge: action === 'purge', confirmKey })
    await refreshAfterLifecycle(app.key)
    ElMessage.success(res.message || (action === 'purge' ? '已彻底清除' : '卸载成功，已即时生效'))
  } catch (e) {
    console.error('uninstall error:', e)
  } finally {
    uninstallingKey.value = ''
  }
}

/** 禁用（软拔）：保留文件与数据，只摘路由/事件/任务 */
async function handleDisable(app: MarketApp) {
  lifecycleKey.value = app.key
  try {
    await disableMarketApp(app.key)
    await refreshAfterLifecycle(app.key)
    ElMessage.success('已禁用（文件与数据保留）')
  } catch (e) {
    console.error('disable error:', e)
  } finally {
    lifecycleKey.value = ''
  }
}

/** 启用（软插）：清 override 并重新挂载 */
async function handleEnable(app: MarketApp) {
  lifecycleKey.value = app.key
  try {
    await enableMarketApp(app.key)
    await refreshAfterLifecycle(app.key)
    notifyWorker(app, '已启用')
  } catch (e) {
    console.error('enable error:', e)
  } finally {
    lifecycleKey.value = ''
  }
}

/** 回滚到最近备份版本 */
async function handleRollback(app: MarketApp) {
  try {
    await ElMessageBox.confirm(
      `将「${app.name}」回滚到上一版本（最近备份）？若旧版与当前数据结构不兼容，会保持在新版本并标记 rollback_blocked。`,
      '确认回滚',
      { confirmButtonText: '确定回滚', cancelButtonText: '取消', type: 'warning' },
    )
  } catch {
    return
  }
  lifecycleKey.value = app.key
  try {
    const res = await rollbackMarketApp(app.key)
    await refreshAfterLifecycle(app.key)
    ElMessage.success(`已回滚到 ${res.to_version}`)
  } catch (e) {
    console.error('rollback error:', e)
  } finally {
    lifecycleKey.value = ''
  }
}

/** 修复：目录丢失/迁移中断/权限丢失 */
async function handleRepair(app: MarketApp) {
  lifecycleKey.value = app.key
  try {
    await repairMarketApp(app.key)
    await refreshAfterLifecycle(app.key)
    ElMessage.success('修复完成')
  } catch (e) {
    console.error('repair error:', e)
  } finally {
    lifecycleKey.value = ''
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
