<template>
  <AdminPage :title="$t('pushMonitor.title')">
    <!-- 统计卡片 -->
    <el-row :gutter="16" class="mb-4">
      <el-col :xs="24" :sm="12" :lg="6" class="mb-4 lg:mb-0">
        <el-card shadow="hover" class="text-center">
          <div class="text-zinc-500 text-xs mb-1">{{ $t('pushMonitor.redisQueue') }}</div>
          <div class="text-2xl font-bold" :class="statusData?.redis.total ? 'text-orange-500' : 'text-green-500'">{{ statusData?.redis.total ?? '-' }}</div>
          <div class="text-zinc-400 text-xs mt-1">{{ $t('pushMonitor.totalBacklog') }}</div>
        </el-card>
      </el-col>
      <el-col v-for="ch in channels" :key="ch.key" :xs="24" :sm="12" :lg="6" class="mb-4 lg:mb-0">
        <el-card shadow="hover" class="text-center">
          <div class="text-zinc-500 text-xs mb-1">{{ ch.label }}</div>
          <div class="text-2xl font-bold" :class="getChannelColor(ch.key)">{{ statusData?.channels[ch.key]?.total ?? '-' }}</div>
          <div class="text-zinc-400 text-xs mt-1">{{ $t('pushMonitor.todayStats') }}</div>
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="16" class="mb-4">
      <el-col :xs="24" :lg="14" class="mb-4 lg:mb-0">
        <el-card>
          <template #header><span class="font-medium">{{ $t('pushMonitor.redisQueue') }}</span></template>
          <div v-for="(len, name) in (statusData?.redis?.queues ?? {})" :key="name" class="mb-3 last:mb-0">
            <div class="flex justify-between text-xs text-zinc-500 mb-1">
              <span>{{ name }}</span>
              <span>{{ len }}</span>
            </div>
            <el-progress :percentage="queuePercent(len)" :color="queueColor(len)" :show-text="false" />
          </div>
        </el-card>
      </el-col>
      <el-col :xs="24" :lg="10">
        <el-card>
          <template #header><span class="font-medium">{{ $t('pushMonitor.healthStatus') }}</span></template>
          <div class="flex items-center gap-3 mb-3">
            <el-tag :type="statusData?.healthy ? 'success' : 'danger'" size="large">
              {{ statusData?.healthy ? $t('pushMonitor.healthy') : $t('pushMonitor.critical') }}
            </el-tag>
            <span class="text-xs text-zinc-400">{{ lastRefresh }}</span>
          </div>
          <div class="space-y-2">
            <div v-for="ch in channels" :key="ch.key" class="flex justify-between text-sm items-center">
              <span>{{ ch.label }}</span>
              <span class="text-xs">
                {{ $t('pushMonitor.success') }}: {{ statusData?.channels[ch.key]?.success ?? 0 }} ·
                {{ $t('pushMonitor.failed') }}: <span :class="(statusData?.channels[ch.key]?.failed ?? 0) > 0 ? 'text-red-500' : ''">{{ statusData?.channels[ch.key]?.failed ?? 0 }}</span> ·
                {{ $t('pushMonitor.successRate') }}: {{ statusData?.channels[ch.key]?.success_rate ?? 0 }}%
              </span>
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <el-card class="mb-4">
      <template #header>
        <div class="flex items-center justify-between">
          <span class="font-medium">{{ $t('pushMonitor.pushLogs') }}</span>
          <el-tabs v-model="logTab" class="!-mb-4" @tab-change="loadLogs">
            <el-tab-pane v-for="ch in channels" :key="ch.key" :label="ch.label" :name="ch.key" />
          </el-tabs>
        </div>
      </template>
      <el-table :data="logItems" stripe size="small" max-height="400">
        <el-table-column prop="created_at" label="时间" width="170">
          <template #default="{ row }">{{ row.created_at ? row.created_at.slice(0, 19).replace('T', ' ') : '-' }}</template>
        </el-table-column>
        <el-table-column prop="event_code" label="事件" width="140" />
        <el-table-column prop="target_kind" label="目标" width="80" />
        <el-table-column prop="title" label="标题" min-width="160" show-overflow-tooltip />
        <el-table-column label="状态" width="90">
          <template #default="{ row }">
            <el-tag :type="row.status === 'success' ? 'success' : row.status === 'failed' ? 'danger' : 'warning'" size="small">{{ row.status }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="error_msg" label="错误" width="120" show-overflow-tooltip />
      </el-table>
      <div class="mt-2 text-center">
        <el-button size="small" @click="loadLogs">{{ $t('pushMonitor.refresh') }}</el-button>
      </div>
    </el-card>

    <el-card>
      <template #header><span class="font-medium">操作</span></template>
      <div class="flex flex-wrap gap-2">
        <el-button v-for="ch in channels" :key="ch.key" type="primary" :loading="testing === ch.key" @click="doTestPush(ch.key)">
          {{ $t('pushMonitor.testPush') }} - {{ ch.label }}
        </el-button>
        <el-popconfirm :title="$t('pushMonitor.clearQueueConfirm')" @confirm="doClearQueue">
          <template #reference>
            <el-button type="danger" :loading="clearing">{{ $t('pushMonitor.clearQueue') }}</el-button>
          </template>
        </el-popconfirm>
        <el-switch v-model="autoRefresh" :active-text="$t('pushMonitor.autoRefresh')" class="ml-4" />
      </div>
    </el-card>
  </AdminPage>
</template>

<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { useI18n } from 'vue-i18n'
import AdminPage from '@/components/admin/AdminPage.vue'
import { pushMonitorApi, type PushStatusOut, type PushLogOut } from '@/api/push-monitor'

const { t } = useI18n()

const channels = [
  { key: 'feishu' as const, label: '飞书' },
  { key: 'wecom' as const, label: '企微' },
  { key: 'dingtalk' as const, label: '钉钉' },
]

const statusData = ref<PushStatusOut | null>(null)
const logItems = ref<PushLogOut[]>([])
const logTab = ref('feishu')
const testing = ref<string | null>(null)
const clearing = ref(false)
const autoRefresh = ref(false)
const lastRefresh = ref('')
let timer: ReturnType<typeof setInterval> | null = null

async function refresh() {
  try {
    const res = await pushMonitorApi.getStatus()
    statusData.value = (res as any).data ?? res
    lastRefresh.value = new Date().toLocaleTimeString()
  } catch { /* */ }
}

async function loadLogs() {
  try {
    const res = await pushMonitorApi.getLogs(logTab.value, { limit: 50 })
    logItems.value = (res as any).data ?? []
  } catch { /* */ }
}

async function doTestPush(ch: string) {
  testing.value = ch
  try {
    await pushMonitorApi.testPush(ch)
    ElMessage.success(t('common.success'))
    refresh()
  } catch {
    ElMessage.error(t('common.failed'))
  } finally {
    testing.value = null
  }
}

async function doClearQueue() {
  clearing.value = true
  try {
    const res = await pushMonitorApi.clearQueue()
    const d = (res as any).data
    ElMessage.success(`${t('pushMonitor.clearQueue')}: ${d?.cleared ?? 0}`)
    refresh()
  } catch {
    ElMessage.error(t('common.failed'))
  } finally {
    clearing.value = false
  }
}

function getChannelColor(ch: string) {
  const s = statusData.value?.channels[ch as keyof typeof statusData.value.channels]
  if (!s) return 'text-zinc-400'
  if (s.failed > 0) return 'text-red-500'
  if (s.pending > 0) return 'text-orange-500'
  return 'text-green-500'
}

function queuePercent(len: number) {
  return Math.min(100, (len / 100) * 100)
}

function queueColor(len: number) {
  if (len > 50) return '#f56c6c'
  if (len > 10) return '#e6a23c'
  return '#67c23a'
}

watch(autoRefresh, (val) => {
  if (val) {
    timer = setInterval(() => { refresh(); loadLogs() }, 30000)
  } else {
    if (timer) clearInterval(timer)
  }
})

onMounted(() => {
  refresh()
  loadLogs()
})

onBeforeUnmount(() => {
  if (timer) clearInterval(timer)
})
</script>
