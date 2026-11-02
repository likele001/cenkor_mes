<!--
  Copyright (C) 2026 CenkorMES Project
  SPDX-License-Identifier: AGPL-3.0
-->
<template>
  <div class="system-about-page p-4 sm:p-6 space-y-6">
    <!-- 当前版本卡片 -->
    <el-card shadow="never" class="version-card">
      <div class="flex items-center gap-4">
        <div class="version-icon shrink-0 w-16 h-16 rounded-2xl bg-gradient-to-br from-blue-500 to-indigo-600 flex items-center justify-center text-white shadow-lg">
          <el-icon :size="32"><InfoFilled /></el-icon>
        </div>
        <div class="flex-1 min-w-0">
          <div class="text-xs text-gray-400 mb-1">{{ t('system.about.currentVersion') }}</div>
          <div class="flex items-center gap-3 flex-wrap">
            <span class="text-2xl font-bold text-gray-800">{{ versionInfo?.version || '--' }}</span>
            <el-tag type="success" size="small" effect="plain">私有化部署</el-tag>
          </div>
          <div class="text-xs text-gray-400 mt-1">
            {{ t('system.about.releaseDate') }}：{{ versionInfo?.release_date || '--' }}
          </div>
        </div>
        <div class="text-right shrink-0 hidden sm:block">
          <div class="text-xs text-gray-400">{{ t('system.about.buildInfo') }}</div>
          <div class="text-sm text-gray-600 mt-0.5">CenkorMES {{ versionInfo?.version }}</div>
        </div>
      </div>
    </el-card>

    <!-- 在线升级 -->
    <el-card shadow="never" class="upgrade-card" v-loading="upgradeLoading">
      <template #header>
        <div class="flex items-center justify-between flex-wrap gap-2">
          <span class="text-base font-semibold text-gray-800">在线升级</span>
          <div class="flex items-center gap-2 flex-wrap">
            <el-button size="small" :loading="upgradeChecking" @click="handleCheckUpgrade">检查更新</el-button>
            <el-button
              size="small"
              type="primary"
              :loading="upgradeStarting"
              :disabled="!upgradeInfo?.latest || upgradeInfo?.working_tree_dirty"
              @click="handleStartUpgrade"
            >
              立即升级
            </el-button>
            <el-button
              size="small"
              type="warning"
              plain
              :loading="upgradeRollingBack"
              :disabled="upgradeInfo?.working_tree_dirty"
              @click="handleRollback"
            >
              回滚上一版
            </el-button>
          </div>
        </div>
      </template>

      <div class="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-4">
        <div class="rounded-lg bg-gray-50 p-3">
          <div class="text-xs text-gray-400">当前版本</div>
          <div class="text-lg font-semibold text-gray-800">
            {{ upgradeInfo?.current || versionInfo?.version || '--' }}
          </div>
        </div>
        <div class="rounded-lg bg-gray-50 p-3">
          <div class="text-xs text-gray-400">可更新版本</div>
          <div class="flex items-center gap-2">
            <span class="text-lg font-semibold" :class="upgradeInfo?.has_update ? 'text-blue-600' : 'text-gray-800'">
              {{ upgradeInfo?.latest || '--' }}
            </span>
            <el-tag v-if="upgradeInfo && upgradeInfo.has_update" size="small" type="success" effect="plain">
              有新版本
            </el-tag>
            <el-tag v-else-if="upgradeInfo" size="small" type="info" effect="plain">已是最新</el-tag>
          </div>
        </div>
        <div class="rounded-lg bg-gray-50 p-3">
          <div class="text-xs text-gray-400">重启方式</div>
          <div class="text-sm mt-0.5 flex items-center gap-2 flex-wrap">
            <el-tag size="small" type="success" effect="plain">
              {{ upgradeInfo?.restart_mode === 'cmd' ? '自动（自定义命令）' : '自动（面板守护进程）' }}
            </el-tag>
            <span v-if="upgradeInfo?.disk_free_gb != null" class="text-xs text-gray-400">
              磁盘余量 {{ upgradeInfo.disk_free_gb }} GB
            </span>
          </div>
        </div>
      </div>

      <el-alert
        v-if="upgradeInfo?.working_tree_dirty"
        type="warning"
        :closable="false"
        show-icon
        class="mb-4"
        title="工作区有未提交改动，已禁用升级/回滚；请先提交或 stash 后再操作。"
      />

      <div class="mb-4">
        <el-checkbox v-model="skipFrontend">
          跳过前端构建（仅更新后端；前端源码有改动时页面不会生效）
        </el-checkbox>
        <div class="text-xs text-gray-400 mt-1">
          默认会检测本次版本是否改动前端，有改动则构建并原子换入 dist，约多花 1~2 分钟。
        </div>
      </div>

      <el-table
        v-if="upgradeJobs.length > 0"
        :data="upgradeJobs"
        size="small"
        border
        style="width: 100%"
        @row-click="openJobLog"
      >
        <el-table-column label="版本" min-width="160">
          <template #default="{ row }">{{ row.from_version }} → {{ row.to_version }}</template>
        </el-table-column>
        <el-table-column label="动作" width="90">
          <template #default="{ row }">
            <el-tag size="small" effect="plain" :type="row.action === 'rollback' ? 'warning' : 'primary'">
              {{ row.action === 'rollback' ? '回滚' : '升级' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="130">
          <template #default="{ row }">
            <el-tag size="small" :type="statusTagType(row.status)">{{ statusLabel(row.status) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="stage" label="阶段" width="110" />
        <el-table-column label="时间" width="180">
          <template #default="{ row }">{{ formatTime(row.started_at) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="130">
          <template #default="{ row }">
            <el-button link type="primary" size="small" @click.stop="openJobLog(row)">日志</el-button>
            <el-button
              v-if="row.status === 'awaiting_restart' || row.status === 'running'"
              link
              type="success"
              size="small"
              @click.stop="handleVerify(row)"
            >
              校验
            </el-button>
          </template>
        </el-table-column>
      </el-table>
      <div v-else class="text-center text-gray-400 py-6 text-sm">暂无升级任务</div>

      <el-dialog v-model="logDialogVisible" :title="`任务 #${logJob?.id ?? ''} 执行日志`" width="720px">
        <div ref="logBoxRef" class="log-box">{{ logContent || '暂无日志' }}</div>
        <template #footer>
          <el-button size="small" :loading="logLoading" @click="refreshLog">刷新</el-button>
          <el-button size="small" type="primary" @click="logDialogVisible = false">关闭</el-button>
        </template>
      </el-dialog>
    </el-card>

    <!-- 开发日志标题 -->
    <div class="flex items-center justify-between">
      <h3 class="text-lg font-semibold text-gray-800">{{ t('system.about.changelog') }}</h3>
      <el-tag size="small" type="info" effect="plain">
        {{ t('system.about.totalVersions', { count: changelog.length }) }}
      </el-tag>
    </div>

    <!-- 开发日志时间线 -->
    <div class="changelog-timeline" v-loading="loading">
      <div v-if="changelog.length === 0 && !loading" class="text-center text-gray-400 py-12">
        {{ t('system.about.noChangelog') }}
      </div>
      <div
        v-for="(item, idx) in changelog"
        :key="item.id"
        class="timeline-item relative pl-8 pb-8"
        :class="{ 'last:pb-0': idx === changelog.length - 1 }"
      >
        <!-- 时间线竖线 -->
        <div
          class="timeline-line absolute left-[11px] top-6 bottom-0 w-0.5"
          :class="idx === changelog.length - 1 ? 'bg-transparent' : 'bg-gray-200'"
        />
        <!-- 时间线圆点 -->
        <div
          class="timeline-dot absolute left-0 top-1.5 w-6 h-6 rounded-full border-2 flex items-center justify-center"
          :class="idx === 0 ? 'border-blue-500 bg-blue-50' : 'border-gray-300 bg-white'"
        >
          <div :class="idx === 0 ? 'w-2 h-2 rounded-full bg-blue-500' : 'w-1.5 h-1.5 rounded-full bg-gray-300'" />
        </div>
        <!-- 内容卡片 -->
        <div
          class="timeline-content rounded-xl border p-4 transition-shadow hover:shadow-sm"
          :class="idx === 0 ? 'border-blue-200 bg-blue-50/30' : 'border-gray-200 bg-white'"
        >
          <div class="flex items-center gap-2 mb-1.5 flex-wrap">
            <span class="font-semibold text-base" :class="idx === 0 ? 'text-blue-700' : 'text-gray-800'">
              {{ item.version }}
            </span>
            <span class="text-xs text-gray-400">{{ item.release_date }}</span>
            <el-tag v-if="idx === 0" size="small" type="success" effect="dark">最新</el-tag>
          </div>
          <p class="text-sm text-gray-600 leading-relaxed whitespace-pre-wrap">{{ item.description }}</p>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, nextTick } from 'vue'
import { useI18n } from 'vue-i18n'
import { InfoFilled } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { systemApi } from '@/api/system'
import type { UpgradeInfoOut, UpgradeJobOut } from '@/api/system'

const { t } = useI18n()

const loading = ref(false)
const versionInfo = ref<{ version: string; release_date: string; description: string } | null>(null)
const changelog = ref<{ id: number; version: string; release_date: string; description: string }[]>([])

onMounted(async () => {
  loading.value = true
  try {
    const [verRes, logRes] = await Promise.all([
      systemApi.getVersionInfo(),
      systemApi.listChangelog({ limit: 200 }),
    ])
    const data = verRes as any
    versionInfo.value = data?.version || null
    changelog.value = (logRes as any)?.items || []
  } catch (e) {
    console.error('获取版本信息失败', e)
  } finally {
    loading.value = false
  }
})
// ── 在线升级 / 回滚 ──────────────────────────────────────────────
const upgradeInfo = ref<UpgradeInfoOut | null>(null)
const upgradeJobs = ref<UpgradeJobOut[]>([])
const upgradeLoading = ref(false)
const upgradeChecking = ref(false)
const upgradeStarting = ref(false)
const skipFrontend = ref(false)
const upgradeRollingBack = ref(false)

const logDialogVisible = ref(false)
const logLoading = ref(false)
const logContent = ref('')
const logJob = ref<UpgradeJobOut | null>(null)
const logBoxRef = ref<HTMLDivElement | null>(null)

const STATUS_LABEL: Record<string, string> = {
  pending: '排队中',
  running: '执行中',
  awaiting_restart: '等待重启',
  success: '成功',
  failed: '失败',
  rolled_back: '已回滚',
}

function statusLabel(status: string) {
  return STATUS_LABEL[status] || status
}

function statusTagType(status: string): 'success' | 'warning' | 'danger' | 'info' | 'primary' {
  if (status === 'success') return 'success'
  if (status === 'failed') return 'danger'
  if (status === 'awaiting_restart') return 'warning'
  if (status === 'running' || status === 'pending') return 'primary'
  return 'info'
}

function formatTime(value: string | null) {
  if (!value) return '--'
  return value.replace('T', ' ').slice(0, 19)
}

async function loadUpgradeState() {
  upgradeLoading.value = true
  try {
    const res = await systemApi.listUpgradeJobs()
    upgradeJobs.value = (res as any)?.items || []
  } catch (e) {
    console.error('获取升级任务失败', e)
  } finally {
    upgradeLoading.value = false
  }
}

async function handleCheckUpgrade() {
  upgradeChecking.value = true
  try {
    upgradeInfo.value = await systemApi.checkUpgrade()
    if (upgradeInfo.value?.has_update) {
      ElMessage.success(`发现新版本 ${upgradeInfo.value.latest}`)
    } else {
      ElMessage.info('当前已是最新版本')
    }
  } catch (e) {
    console.error('检查更新失败', e)
  } finally {
    upgradeChecking.value = false
  }
}

async function handleStartUpgrade() {
  const target = upgradeInfo.value?.latest || ''
  if (!target) {
    ElMessage.warning('请先点击「检查更新」确认目标版本')
    return
  }
  const restartTip =
    upgradeInfo.value?.restart_mode === 'cmd'
      ? '服务将执行自定义重启命令并通过健康校验，约 1~3 分钟。'
      : '服务会自动重启（旧进程退出后由面板守护进程拉起）并通过健康校验，约 1~3 分钟。'
  try {
    await ElMessageBox.confirm(
      `确认升级到 ${target}？升级前会自动备份数据库，过程中服务可能短暂不可用。${restartTip}`,
      '确认在线升级',
      { type: 'warning', confirmButtonText: '确认升级', cancelButtonText: '取消' },
    )
  } catch {
    return
  }
  upgradeStarting.value = true
  try {
    await systemApi.startUpgrade({ target_version: target, skip_frontend: skipFrontend.value })
    ElMessage.success('升级任务已启动')
    await loadUpgradeState()
  } catch (e) {
    console.error('启动升级失败', e)
  } finally {
    upgradeStarting.value = false
  }
}

async function handleRollback() {
  const candidate = upgradeJobs.value.find((x) => x.status === 'failed') || upgradeJobs.value[0]
  if (!candidate) {
    ElMessage.warning('暂无可用作回滚点的任务')
    return
  }
  try {
    await ElMessageBox.confirm(
      `将以任务 #${candidate.id} 记录的回滚点（${candidate.from_ref ? candidate.from_ref.slice(0, 8) : '无'}）回滚代码，可能覆盖当前代码改动。` +
        '若上一次升级已执行数据库迁移，仅回滚代码可能造成版本不一致，请评估后再操作。',
      '确认回滚',
      { type: 'warning', confirmButtonText: '确认回滚', cancelButtonText: '取消' },
    )
  } catch {
    return
  }
  upgradeRollingBack.value = true
  try {
    await systemApi.rollbackUpgrade({ job_id: candidate.id, restore_db: false })
    ElMessage.success('回滚任务已启动')
    await loadUpgradeState()
  } catch (e) {
    console.error('回滚失败', e)
  } finally {
    upgradeRollingBack.value = false
  }
}

async function handleVerify(row: UpgradeJobOut) {
  try {
    const res = await systemApi.verifyUpgradeJob(row.id)
    if (res.healthy) {
      ElMessage.success(`健康校验通过：${res.actual}`)
    } else {
      ElMessage.error(`健康校验失败：期望 ${res.expected}，实际 ${res.actual || '无响应'}`)
    }
    await loadUpgradeState()
  } catch (e) {
    console.error('健康校验失败', e)
  }
}

async function openJobLog(row: UpgradeJobOut) {
  logJob.value = row
  logContent.value = ''
  logDialogVisible.value = true
  await refreshLog()
}

async function refreshLog() {
  if (!logJob.value) return
  logLoading.value = true
  try {
    const res = await systemApi.getUpgradeJobLog(logJob.value.id, { offset: 0, limit: 10000 })
    logContent.value = res.content || ''
    await nextTick()
    if (logBoxRef.value) logBoxRef.value.scrollTop = logBoxRef.value.scrollHeight
  } catch (e) {
    console.error('读取日志失败', e)
  } finally {
    logLoading.value = false
  }
}

onMounted(loadUpgradeState)

</script>

<style scoped>
.timeline-item:last-child .timeline-line {
  display: none;
}

.log-box {
  max-height: 420px;
  overflow: auto;
  background: #0b1020;
  color: #d6e4ff;
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  font-size: 12px;
  line-height: 1.6;
  padding: 12px;
  border-radius: 8px;
  white-space: pre-wrap;
  word-break: break-all;
}
</style>