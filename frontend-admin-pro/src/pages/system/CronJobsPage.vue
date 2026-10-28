<!--
  Copyright (C) 2026 CenkorMES Project
  SPDX-License-Identifier: AGPL-3.0
-->
<template>
  <AdminPage :title="$t('cronJobs.title')">
    <el-alert
      v-if="saasMode"
      type="info"
      :closable="false"
      class="mb-3"
      :title="$t('cronJobs.saasReadonlyTip')"
    />

    <div class="grid grid-cols-1 xl:grid-cols-2 gap-3 mb-3">
      <!-- 任务执行器（Celery Worker）：状态 + 优雅重启 -->
      <el-card>
        <template #header>
          <div class="flex items-center justify-between">
            <span class="font-medium">{{ $t('cronJobs.workerTitle') }}</span>
            <div class="flex items-center gap-2">
              <el-button size="small" :loading="workerLoading" @click="loadWorker">
                {{ $t('cronJobs.workerRefresh') }}
              </el-button>
              <el-button
                size="small"
                type="warning"
                :loading="workerRestarting"
                :disabled="saasMode || !workerOnline"
                @click="doRestartWorker"
              >
                {{ $t('cronJobs.workerRestart') }}
              </el-button>
            </div>
          </div>
        </template>
        <div v-loading="workerLoading" class="text-sm space-y-2">
          <template v-if="workerStatus">
            <div v-if="workerStatus.configured === false" class="flex flex-wrap items-center gap-2">
              <el-tag type="info" size="small">{{ $t('cronJobs.workerUnmanaged') }}</el-tag>
              <span class="text-xs text-zinc-500">{{ $t('cronJobs.workerUnmanagedHint') }}</span>
            </div>
            <template v-else-if="workerStatus.ok && workerStatus.workers.length">
              <div
                v-for="w in workerStatus.workers"
                :key="w.hostname"
                class="flex flex-wrap items-center gap-2"
              >
                <el-tag type="success" size="small">{{ $t('cronJobs.workerOnline') }}</el-tag>
                <span class="font-mono text-xs">{{ w.hostname }}</span>
                <span class="text-xs text-zinc-500">{{ $t('cronJobs.workerActive') }}: {{ w.active_count }}</span>
                <span v-if="w.active_tasks.length" class="text-xs text-zinc-400">
                  {{ w.active_tasks.map((x) => x.name).filter(Boolean).join(' / ') }}
                </span>
              </div>
            </template>
            <div v-else-if="workerStatus.ok" class="flex flex-wrap items-center gap-2">
              <el-tag type="danger" size="small">{{ $t('cronJobs.workerOffline') }}</el-tag>
              <span class="text-xs text-zinc-500">
                {{ $t('cronJobs.workerOfflineHint', { prefix: workerStatus.prefix || '-', service: workerStatus.service || '-' }) }}
              </span>
            </div>
            <div v-else class="text-xs text-red-500">{{ workerStatus.error || $t('common.failed') }}</div>
            <div class="text-xs text-zinc-400">{{ $t('cronJobs.workerHint') }}</div>
          </template>
        </div>
      </el-card>

      <!-- 调度器（Celery Beat）：systemd 单元状态 + 重启 -->
      <el-card>
        <template #header>
          <div class="flex items-center justify-between">
            <span class="font-medium">{{ $t('cronJobs.beatTitle') }}</span>
            <div class="flex items-center gap-2">
              <el-button size="small" :loading="beatLoading" @click="loadBeat">
                {{ $t('cronJobs.beatRefresh') }}
              </el-button>
              <el-button
                size="small"
                type="warning"
                :loading="beatRestarting"
                :disabled="saasMode || !beatStatus || beatStatus.configured === false || beatStatus.installed === false"
                @click="doRestartBeat"
              >
                {{ $t('cronJobs.beatRestart') }}
              </el-button>
            </div>
          </div>
        </template>
        <div v-loading="beatLoading" class="text-sm space-y-2">
          <template v-if="beatStatus">
            <div class="flex flex-wrap items-center gap-2">
              <el-tag :type="beatTagType" size="small">{{ beatStateText }}</el-tag>
              <span class="font-mono text-xs">{{ beatStatus.unit || '-' }}</span>
              <span class="text-xs text-zinc-500">{{ $t('cronJobs.beatState') }}: {{ beatStatus.state }}</span>
            </div>
            <div v-if="beatStatus.active" class="text-xs text-zinc-500">
              {{ $t('cronJobs.beatStartedAt') }}: {{ fmtTime(beatStatus.started_at) }}
              <span class="ml-3">{{ $t('cronJobs.beatUptime') }}: {{ fmtUptime(beatStatus.uptime_seconds) }}</span>
            </div>
            <div v-else-if="beatStatus.configured === false" class="text-xs text-zinc-500">
              {{ $t('cronJobs.beatUnmanagedHint') }}
            </div>
            <div v-else-if="beatStatus.installed === false" class="text-xs text-amber-600">
              {{ $t('cronJobs.beatNotInstalledHint', { unit: beatStatus.unit }) }}
            </div>
            <div class="text-xs text-zinc-400">{{ $t('cronJobs.beatHint', { unit: beatStatus.unit || '-' }) }}</div>
          </template>
        </div>
      </el-card>
    </div>

    <el-card>
      <template #header>
        <div class="flex items-center justify-between">
          <span class="font-medium">{{ $t('cronJobs.list') }}</span>
          <el-button size="small" :loading="reloading" @click="doReload">{{ $t('cronJobs.reload') }}</el-button>
        </div>
      </template>
      <el-table :data="items" stripe size="small" v-loading="loading">
        <el-table-column prop="name" :label="$t('cronJobs.name')" width="200" show-overflow-tooltip />
        <el-table-column prop="description" :label="$t('cronJobs.description')" min-width="140" show-overflow-tooltip />
        <el-table-column :label="$t('cronJobs.cronExpression')" min-width="240">
          <template #default="{ row }">
            <el-tag size="small" effect="plain" class="font-mono text-xs">
              {{ row.cron_minute }} {{ row.cron_hour }} {{ row.cron_day_of_month }} {{ row.cron_month_of_year }} {{ row.cron_day_of_week }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column :label="$t('cronJobs.enabled')" width="70" align="center">
          <template #default="{ row }">
            <el-switch :model-value="row.enabled" size="small" @change="(v: boolean) => quickToggle(row, v)" />
          </template>
        </el-table-column>
        <el-table-column prop="last_run_at" :label="$t('cronJobs.lastRun')" width="150">
          <template #default="{ row }">{{ row.last_run_at ? row.last_run_at.slice(0, 19).replace('T', ' ') : '-' }}</template>
        </el-table-column>
        <el-table-column :label="$t('cronJobs.actions')" width="80" align="center" fixed="right">
          <template #default="{ row }">
            <el-button type="primary" link size="small" @click="openEdit(row)">{{ $t('common.edit') }}</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 编辑弹窗 -->
    <el-dialog :model-value="editOpen" :title="$t('cronJobs.edit')" width="520px" destroy-on-close @update:model-value="editOpen = $event">
      <div v-if="editRow" class="space-y-4">
        <el-form-item :label="$t('cronJobs.name')">
          <el-input :model-value="editRow.name" disabled />
        </el-form-item>
        <el-form-item v-if="!editRow.is_system" :label="$t('cronJobs.description')">
          <el-input v-model="editForm.description" />
        </el-form-item>
        <el-form-item :label="$t('cronJobs.enabled')">
          <el-switch v-model="editForm.enabled" />
        </el-form-item>
        <div class="text-sm font-medium text-zinc-700 mb-1">{{ $t('cronJobs.cronExpression') }}</div>
        <div class="grid grid-cols-5 gap-2">
          <div>
            <div class="text-xs text-zinc-400 mb-1">{{ $t('cronJobs.minute') }}</div>
            <el-input v-model="editForm.cron_minute" size="small" />
          </div>
          <div>
            <div class="text-xs text-zinc-400 mb-1">{{ $t('cronJobs.hour') }}</div>
            <el-input v-model="editForm.cron_hour" size="small" />
          </div>
          <div>
            <div class="text-xs text-zinc-400 mb-1">{{ $t('cronJobs.day') }}</div>
            <el-input v-model="editForm.cron_day_of_month" size="small" />
          </div>
          <div>
            <div class="text-xs text-zinc-400 mb-1">{{ $t('cronJobs.month') }}</div>
            <el-input v-model="editForm.cron_month_of_year" size="small" />
          </div>
          <div>
            <div class="text-xs text-zinc-400 mb-1">{{ $t('cronJobs.week') }}</div>
            <el-input v-model="editForm.cron_day_of_week" size="small" />
          </div>
        </div>
        <div class="text-xs text-zinc-400">{{ $t('cronJobs.cronHint') }}</div>
      </div>
      <template #footer>
        <el-button @click="editOpen = false">{{ $t('common.cancel') }}</el-button>
        <el-button type="primary" :loading="saving" @click="doSave">{{ $t('common.save') }}</el-button>
      </template>
    </el-dialog>
  </AdminPage>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useI18n } from 'vue-i18n'
import AdminPage from '@/components/admin/AdminPage.vue'
import {
  cronJobsApi,
  type BeatStatusOut,
  type CronJobOut,
  type WorkerStatusOut,
} from '@/api/cron-jobs'

const { t } = useI18n()

const items = ref<CronJobOut[]>([])
const loading = ref(false)
const reloading = ref(false)
/** SaaS 模式下 Worker/Beat 属部署级运维，重启收敛平台端，本页只读 */
const saasMode = ref(false)

const editOpen = ref(false)
const editRow = ref<CronJobOut | null>(null)
const editForm = ref({
  enabled: true,
  description: '',
  cron_minute: '*',
  cron_hour: '*',
  cron_day_of_month: '*',
  cron_month_of_year: '*',
  cron_day_of_week: '*',
})
const saving = ref(false)

const workerStatus = ref<WorkerStatusOut | null>(null)
const workerLoading = ref(false)
const workerRestarting = ref(false)
const workerOnline = computed(
  () =>
    workerStatus.value?.configured !== false &&
    !!workerStatus.value?.ok &&
    (workerStatus.value?.workers.length ?? 0) > 0,
)

const beatStatus = ref<BeatStatusOut | null>(null)
const beatLoading = ref(false)
const beatRestarting = ref(false)
const beatStateText = computed(() => {
  if (!beatStatus.value) return t('cronJobs.beatStopped')
  if (beatStatus.value.configured === false) return t('cronJobs.beatUnmanaged')
  if (beatStatus.value.active) return t('cronJobs.beatRunning')
  if (beatStatus.value.installed === false) return t('cronJobs.beatNotInstalled')
  return t('cronJobs.beatStopped')
})
const beatTagType = computed(() => {
  if (!beatStatus.value) return 'info' as const
  if (beatStatus.value.configured === false) return 'info' as const
  if (beatStatus.value.active) return 'success' as const
  if (beatStatus.value.installed === false) return 'warning' as const
  return 'danger' as const
})

function fmtTime(value?: string | null) {
  if (!value) return '-'
  const d = new Date(value)
  return Number.isNaN(d.getTime()) ? value : d.toLocaleString()
}

function fmtUptime(seconds?: number | null) {
  if (seconds == null) return '-'
  if (seconds < 60) return `${seconds}s`
  const minutes = Math.floor(seconds / 60)
  if (minutes < 60) return `${minutes}m`
  const hours = Math.floor(minutes / 60)
  if (hours < 24) return `${hours}h ${minutes % 60}m`
  return `${Math.floor(hours / 24)}d ${hours % 24}h`
}

async function loadWorker() {
  workerLoading.value = true
  try {
    workerStatus.value = await cronJobsApi.workerStatus()
  } catch {
    workerStatus.value = { ok: false, workers: [], error: t('common.failed') }
  } finally {
    workerLoading.value = false
  }
}

async function loadBeat() {
  beatLoading.value = true
  try {
    beatStatus.value = await cronJobsApi.beatStatus()
  } catch {
    beatStatus.value = null
  } finally {
    beatLoading.value = false
  }
}

async function doRestartWorker() {
  try {
    await ElMessageBox.confirm(t('cronJobs.workerRestartConfirm'), t('cronJobs.workerRestart'), {
      type: 'warning',
      confirmButtonText: t('common.confirm'),
      cancelButtonText: t('common.cancel'),
    })
  } catch {
    return
  }
  workerRestarting.value = true
  try {
    await cronJobsApi.workerRestart()
    ElMessage.success(t('cronJobs.workerRestarting'))
    setTimeout(loadWorker, 8000)
  } catch {
    // 失败提示由 http 层统一弹出（含后端 503 的 detail 文案）
  } finally {
    workerRestarting.value = false
  }
}

async function doRestartBeat() {
  try {
    await ElMessageBox.confirm(
      t('cronJobs.beatRestartConfirm', { unit: beatStatus.value?.unit || '-' }),
      t('cronJobs.beatRestart'),
      {
        type: 'warning',
        confirmButtonText: t('common.confirm'),
        cancelButtonText: t('common.cancel'),
      },
    )
  } catch {
    return
  }
  beatRestarting.value = true
  try {
    await cronJobsApi.beatRestart()
    ElMessage.success(t('cronJobs.beatRestarting'))
    setTimeout(loadBeat, 3000)
  } catch {
    // 失败提示由 http 层统一弹出
  } finally {
    beatRestarting.value = false
  }
}

async function load() {
  loading.value = true
  try {
    const res = await cronJobsApi.list()
    items.value = res.items ?? []
    saasMode.value = !!res.saas_mode
  } finally {
    loading.value = false
  }
}

async function doReload() {
  reloading.value = true
  try {
    await cronJobsApi.reload()
    ElMessage.success(t('cronJobs.reloaded'))
    load()
  } finally {
    reloading.value = false
  }
}

function openEdit(row: CronJobOut) {
  editRow.value = row
  editForm.value = {
    enabled: row.enabled,
    description: row.description ?? '',
    cron_minute: row.cron_minute,
    cron_hour: row.cron_hour,
    cron_day_of_month: row.cron_day_of_month,
    cron_month_of_year: row.cron_month_of_year,
    cron_day_of_week: row.cron_day_of_week,
  }
  editOpen.value = true
}

async function doSave() {
  if (!editRow.value) return
  saving.value = true
  try {
    await cronJobsApi.update(editRow.value.id, editForm.value)
    ElMessage.success(t('cronJobs.saved'))
    editOpen.value = false
    load()
  } finally {
    saving.value = false
  }
}

async function quickToggle(row: CronJobOut, v: boolean) {
  try {
    await cronJobsApi.update(row.id, { enabled: v })
    row.enabled = v
    ElMessage.success(t('common.success'))
  } catch {
    ElMessage.error(t('common.failed'))
  }
}

onMounted(() => {
  load()
  loadWorker()
  loadBeat()
})
</script>
