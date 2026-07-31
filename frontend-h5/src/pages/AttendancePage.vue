<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { closeToast, showLoadingToast, showToast } from 'vant'
import { checkIn, checkOut, getAttendanceGeofence, listMyAttendance, type H5AttendanceRecord } from '@/api/tasks'

const loading = ref(false)
const records = ref<H5AttendanceRecord[]>([])
const geofence = ref<{ enabled: boolean; radius_m?: number }>({ enabled: false })

const today = computed(() => {
  const d = new Date()
  const y = d.getFullYear()
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  const weekdays = ['日', '一', '二', '三', '四', '五', '六']
  return { str: `${y}-${m}-${day}`, weekday: weekdays[d.getDay()], label: `${y}年${m}月${day}日` }
})

// 本月统计
const monthStats = computed(() => {
  const month = today.value.str.slice(0, 7)
  const monthRecs = records.value.filter((r) => r.work_date?.startsWith(month))
  const workDays = monthRecs.length
  const totalMinutes = monthRecs.reduce((a, r) => a + (r.minutes || 0), 0)
  return { workDays, totalMinutes }
})

// 今日打卡状态
const todayRecord = computed(() => {
  return records.value.find((r) => r.work_date === today.value.str) || null
})

const todayStatus = computed(() => {
  const r = todayRecord.value
  if (!r) return { label: '未打卡', type: 'default' as const }
  if (!r.check_out_at) return { label: '已上班未下班', type: 'warning' as const }
  return { label: '已打卡', type: 'success' as const }
})

const canCheckIn = computed(() => {
  return !todayRecord.value?.check_in_at
})

const canCheckOut = computed(() => {
  return todayRecord.value?.check_in_at && !todayRecord.value?.check_out_at
})

function fmtMin(v: number | null | undefined) {
  if (v === null || v === undefined) return '—'
  const h = Math.floor(v / 60)
  const m = v % 60
  return h > 0 ? `${h}h${m}min` : `${m}min`
}

function fmtTime(v: string | null | undefined) {
  if (!v) return '—'
  return v.slice(11, 19)
}

async function refresh() {
  loading.value = true
  try {
    const [res, geo] = await Promise.all([
      listMyAttendance({ offset: 0, limit: 60 }),
      getAttendanceGeofence().catch(() => ({ enabled: false })),
    ])
    records.value = res.items ?? []
    geofence.value = geo
  } finally {
    loading.value = false
  }
}

async function doCheckIn() {
  showLoadingToast({ message: '打卡中...', duration: 0 })
  try {
    await checkIn()
    showToast('上班打卡成功')
    await refresh()
  } catch {
    showToast('打卡失败')
  } finally {
    closeToast()
  }
}

async function doCheckOut() {
  showLoadingToast({ message: '打卡中...', duration: 0 })
  try {
    await checkOut()
    showToast('下班打卡成功')
    await refresh()
  } catch {
    showToast('打卡失败')
  } finally {
    closeToast()
  }
}

onMounted(refresh)
</script>

<template>
  <div>
    <!-- 打卡头部 -->
    <div class="rounded-xl bg-gradient-to-r from-blue-500 to-cyan-500 p-4 text-white">
      <div class="flex items-center justify-between">
        <div>
          <div class="text-sm opacity-80">{{ today.label }} 星期{{ today.weekday }}</div>
          <div class="mt-2 text-lg font-semibold">考勤打卡</div>
          <div v-if="geofence.enabled" class="mt-1 text-xs opacity-80">已启用 GPS 围栏（允许半径 {{ geofence.radius_m || 200 }} 米）</div>
        </div>
        <van-tag :type="todayStatus.type" plain size="medium" class="!text-white !border-white/60">
          {{ todayStatus.label }}
        </van-tag>
      </div>
    </div>

    <!-- 打卡按钮 -->
    <div class="mx-4 -mt-2 grid grid-cols-2 gap-3">
      <van-button
        block
        round
        size="large"
        type="primary"
        :disabled="!canCheckIn"
        :loading="loading"
        @click="doCheckIn"
      >
        <template #icon>
          <svg class="h-5 w-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M12 4v16m8-8H4" />
          </svg>
        </template>
        上班打卡
      </van-button>
      <van-button
        block
        round
        size="large"
        plain
        type="primary"
        :disabled="!canCheckOut"
        :loading="loading"
        @click="doCheckOut"
      >
        <template #icon>
          <svg class="h-5 w-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M12 4v16m8-8H4" />
          </svg>
        </template>
        下班打卡
      </van-button>
    </div>

    <!-- 月度统计 -->
    <div class="mx-4 mt-4">
      <div class="mb-2 text-sm font-medium text-zinc-700">本月统计</div>
      <div class="grid grid-cols-3 gap-3">
        <div class="rounded-xl bg-white p-3 text-center shadow-sm">
          <div class="text-xs text-zinc-500">出勤天数</div>
          <div class="mt-1 text-lg font-bold text-blue-600">{{ monthStats.workDays }}</div>
        </div>
        <div class="rounded-xl bg-white p-3 text-center shadow-sm">
          <div class="text-xs text-zinc-500">总工时</div>
          <div class="mt-1 text-lg font-bold text-zinc-900">{{ fmtMin(monthStats.totalMinutes) }}</div>
        </div>
        <div class="rounded-xl bg-white p-3 text-center shadow-sm">
          <div class="text-xs text-zinc-500">平均工时/天</div>
          <div class="mt-1 text-lg font-bold text-green-600">
            {{ monthStats.workDays > 0 ? fmtMin(Math.round(monthStats.totalMinutes / monthStats.workDays)) : '—' }}
          </div>
        </div>
      </div>
    </div>

    <!-- 今日打卡详情 -->
    <div v-if="todayRecord" class="mx-4 mt-4">
      <div class="mb-2 text-sm font-medium text-zinc-700">今日打卡</div>
      <div class="rounded-xl bg-white p-3 shadow-sm">
        <div class="flex items-center justify-between text-sm">
          <div class="flex items-center gap-2">
            <div class="h-2 w-2 rounded-full bg-green-500" />
            <span>上班</span>
          </div>
          <span class="font-mono">{{ fmtTime(todayRecord.check_in_at) }}</span>
        </div>
        <div class="mt-3 flex items-center justify-between text-sm">
          <div class="flex items-center gap-2">
            <div class="h-2 w-2 rounded-full" :class="todayRecord.check_out_at ? 'bg-green-500' : 'bg-zinc-300'" />
            <span>下班</span>
          </div>
          <span class="font-mono">{{ todayRecord.check_out_at ? fmtTime(todayRecord.check_out_at) : '未打卡' }}</span>
        </div>
        <div v-if="todayRecord.check_in_lat != null" class="mt-2 text-xs text-zinc-400">
          上班定位：{{ todayRecord.check_in_lat?.toFixed(5) }}, {{ todayRecord.check_in_lng?.toFixed(5) }}
        </div>
        <div v-if="todayRecord.minutes" class="mt-3 border-t border-zinc-100 pt-3 text-center text-sm text-zinc-500">
          今日工时：<span class="font-semibold text-zinc-800">{{ fmtMin(todayRecord.minutes) }}</span>
        </div>
      </div>
    </div>

    <!-- 最近记录 -->
    <div class="mx-4 mt-4">
      <div class="mb-2 text-sm font-medium text-zinc-700">最近记录</div>
      <van-list :loading="loading" finished>
        <van-cell-group v-if="records.length" inset>
          <van-cell v-for="r in records" :key="r.id">
            <template #title>
              <div class="flex items-center gap-2">
                <span class="text-sm">{{ r.work_date }}</span>
                <van-tag
                  v-if="!r.check_out_at"
                  type="warning"
                  size="medium"
                  plain
                >未下班</van-tag>
              </div>
            </template>
            <template #label>
              <div class="text-xs text-zinc-400">
                上班：{{ fmtTime(r.check_in_at) }}　下班：{{ fmtTime(r.check_out_at) }}
              </div>
            </template>
            <template #value>
              <span class="text-xs">{{ fmtMin(r.minutes) }}</span>
            </template>
          </van-cell>
        </van-cell-group>
        <van-empty v-else description="暂无记录" />
      </van-list>
    </div>

    <div class="h-8" />
  </div>
</template>
