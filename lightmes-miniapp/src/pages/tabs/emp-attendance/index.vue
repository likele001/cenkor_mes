<template>
  <view class="emp-page">
    <view class="emp-page-head">
      <text class="emp-page-title">考勤打卡</text>
    </view>

    <!-- 今日状态卡 -->
    <view class="emp-card emp-card--brand today-card">
      <view class="today-head">
        <view>
          <text class="today-date">{{ todayStr }}</text>
          <text class="today-weekday">{{ weekdayStr }}</text>
        </view>
        <view class="today-status-pill" :class="todayStatusClass">
          <view class="status-dot" />
          <text>{{ todayStatusText }}</text>
        </view>
      </view>

      <view class="today-times">
        <view class="time-block">
          <text class="time-label">上班</text>
          <text class="time-value">{{ todayIn || '--:--' }}</text>
        </view>
        <view class="time-arrow">→</view>
        <view class="time-block">
          <text class="time-label">下班</text>
          <text class="time-value">{{ todayOut || '--:--' }}</text>
        </view>
        <view class="time-block hours-block">
          <text class="time-label">工时</text>
          <text class="time-value hours">{{ todayMinutes ? formatHours(todayMinutes) : '—' }}</text>
        </view>
      </view>
    </view>

    <!-- 打卡按钮 -->
    <view class="emp-card actions">
      <button class="emp-btn-primary" :loading="loading" :disabled="!!todayIn" @tap="checkIn">
        {{ todayIn ? '已打卡' : '上班打卡' }}
      </button>
      <button class="emp-btn-primary out-btn" :loading="loading" :disabled="!todayIn || !!todayOut" @tap="checkOut">
        {{ todayOut ? '已打卡' : '下班打卡' }}
      </button>
    </view>

    <!-- 月度统计 -->
    <view class="emp-card">
      <view class="overview-top">
        <text class="emp-section-title">月度统计</text>
        <picker mode="date" fields="month" :value="month" @change="onMonth">
          <text class="month-pick">{{ monthLabel }} ›</text>
        </picker>
      </view>
      <view class="emp-stat-grid">
        <view class="stat-item">
          <view class="stat-val">{{ monthStats.days }}</view>
          <view class="stat-lbl">出勤天数</view>
        </view>
        <view class="stat-item">
          <view class="stat-val">{{ monthStats.avgHours }}</view>
          <view class="stat-lbl">平均工时(h)</view>
        </view>
        <view class="stat-item">
          <view class="stat-val">{{ monthStats.totalMinutes }}</view>
          <view class="stat-lbl">总工时(分)</view>
        </view>
      </view>
    </view>

    <!-- 打卡记录 -->
    <view class="section-head">打卡记录</view>
    <view v-if="!records.length && !loading" class="emp-empty">
      <text class="emp-empty-icon">◌</text>
      暂无打卡记录
    </view>
    <view v-for="r in records" :key="r.id" class="emp-card emp-card--striped record-card" :class="getRecordStrip(r)">
      <view class="record-head">
        <view class="record-date-row">
          <text class="record-date">{{ r.work_date }}</text>
          <text class="record-weekday">{{ getWeekday(r.work_date) }}</text>
        </view>
        <text class="emp-tag" :class="getRecordTag(r).tone">{{ getRecordTag(r).text }}</text>
      </view>
      <view class="record-times">
        <view class="record-time-item">
          <text class="rt-label">上班</text>
          <text class="rt-value">{{ formatTime(r.check_in_at) }}</text>
        </view>
        <view class="record-time-item">
          <text class="rt-label">下班</text>
          <text class="rt-value">{{ formatTime(r.check_out_at) }}</text>
        </view>
        <view class="record-time-item">
          <text class="rt-label">工时</text>
          <text class="rt-value accent">{{ r.minutes ? formatHours(r.minutes) : '—' }}</text>
        </view>
      </view>
      <view v-if="r.remark" class="record-remark">备注：{{ r.remark }}</view>
    </view>
  </view>
</template>

<script setup lang="ts">
import { onShow } from '@dcloudio/uni-app'
import { computed, ref } from 'vue'
import { checkIn as apiIn, checkOut as apiOut, getAttendanceRecords, type AttendanceRecord } from '@/api/h5/attendance'

const WEEKDAYS = ['周日', '周一', '周二', '周三', '周四', '周五', '周六']
const now = new Date()
const todayDateStr = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-${String(now.getDate()).padStart(2, '0')}`

const records = ref<AttendanceRecord[]>([])
const loading = ref(false)
const month = ref(`${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}`)

const monthLabel = computed(() => {
  const [y, m] = month.value.split('-')
  return `${y}年${m}月`
})

const todayStr = computed(() => {
  const d = new Date()
  return `${d.getMonth() + 1}月${d.getDate()}日`
})

const weekdayStr = computed(() => WEEKDAYS[new Date().getDay()])

const todayRecord = computed(() => records.value.find((r) => r.work_date === todayDateStr) || null)
const todayIn = computed(() => todayRecord.value?.check_in_at ? formatTime(todayRecord.value.check_in_at) : '')
const todayOut = computed(() => todayRecord.value?.check_out_at ? formatTime(todayRecord.value.check_out_at) : '')
const todayMinutes = computed(() => todayRecord.value?.minutes ?? 0)

const todayStatusText = computed(() => {
  if (!todayRecord.value) return '今日未打卡'
  if (todayRecord.value.check_in_at && todayRecord.value.check_out_at) return '已完成'
  if (todayRecord.value.check_in_at) return '上班中'
  return '已记录'
})

const todayStatusClass = computed(() => {
  if (!todayRecord.value) return 'none'
  if (todayRecord.value.check_out_at) return 'done'
  if (todayRecord.value.check_in_at) return 'working'
  return 'none'
})

const monthStats = computed(() => {
  const list = records.value.filter((r) => r.minutes && r.minutes > 0)
  const days = list.length
  const totalMin = list.reduce((s, r) => s + (r.minutes || 0), 0)
  const avgH = days ? (totalMin / days / 60).toFixed(1) : '0.0'
  return { days, avgHours: avgH, totalMinutes: totalMin }
})

onShow(() => load())

async function load() {
  loading.value = true
  try {
    const r = await getAttendanceRecords({ limit: 60, month: month.value || undefined })
    records.value = r.items || []
  } catch {
    records.value = []
  } finally {
    loading.value = false
  }
}

function onMonth(e: { detail: { value: string } }) {
  month.value = e.detail.value.slice(0, 7)
  load()
}

async function checkIn() {
  loading.value = true
  try {
    await apiIn()
    uni.showToast({ title: '上班打卡成功', icon: 'success' })
    load()
  } finally {
    loading.value = false
  }
}

async function checkOut() {
  loading.value = true
  try {
    await apiOut()
    uni.showToast({ title: '下班打卡成功', icon: 'success' })
    load()
  } finally {
    loading.value = false
  }
}

function formatTime(dt: string | null) {
  if (!dt) return '--:--'
  const d = new Date(dt)
  return `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`
}

function formatHours(minutes: number) {
  const h = Math.floor(minutes / 60)
  const m = minutes % 60
  return m > 0 ? `${h}h${m}m` : `${h}h`
}

function getWeekday(dateStr: string) {
  const d = new Date(dateStr + 'T00:00:00')
  return WEEKDAYS[d.getDay()]
}

function getRecordTag(r: AttendanceRecord) {
  if (!r.check_in_at) return { text: '缺卡', tone: 'warn' }
  if (r.check_in_at && !r.check_out_at) return { text: '未下班', tone: 'info' }
  if (r.minutes && r.minutes >= 480) return { text: '正常', tone: 'ok' }
  if (r.minutes && r.minutes < 480) return { text: '工时不足', tone: 'warn' }
  return { text: '已出勤', tone: 'ok' }
}

function getRecordStrip(r: AttendanceRecord) {
  if (!r.check_in_at) return 'strip-warn'
  if (r.check_in_at && !r.check_out_at) return 'strip-info'
  if (r.minutes && r.minutes < 480) return 'strip-pending'
  return 'strip-done'
}
</script>

<style scoped lang="scss">
// 今日卡（品牌渐变）
.today-card {
  padding: $space-6;
  border-radius: $radius-xl;
}
.today-head {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: $space-5;
}
.today-date {
  font-size: $text-xl;
  font-weight: $fw-bold;
  color: #fff;
  display: block;
  letter-spacing: -0.3rpx;
}
.today-weekday {
  font-size: $text-sm;
  color: rgba(255, 255, 255, 0.78);
  margin-top: 4rpx;
  display: block;
}
.today-status-pill {
  display: inline-flex;
  align-items: center;
  gap: 8rpx;
  background: rgba(255, 255, 255, 0.18);
  backdrop-filter: blur(8rpx);
  border: 1rpx solid rgba(255, 255, 255, 0.25);
  padding: 8rpx 20rpx;
  border-radius: $radius-pill;
  font-size: $text-xs;
  color: #fff;
  font-weight: $fw-semibold;
}
.status-dot {
  width: 12rpx;
  height: 12rpx;
  border-radius: 50%;
  background: #fff;
}
.today-status-pill.working .status-dot {
  background: #34d399;
  box-shadow: 0 0 0 4rpx rgba(52, 211, 153, 0.4);
  animation: pulse 2s infinite;
}
.today-status-pill.done .status-dot { background: #60a5fa; }
.today-status-pill.none .status-dot { background: #fbbf24; }
@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
}
.today-times {
  display: flex;
  align-items: center;
  gap: $space-3;
  background: rgba(255, 255, 255, 0.12);
  border-radius: $radius-lg;
  padding: $space-5 $space-4;
  backdrop-filter: blur(8rpx);
}
.time-block {
  flex: 1;
  text-align: center;
}
.hours-block {
  flex: 0.85;
  border-left: 1rpx solid rgba(255, 255, 255, 0.2);
}
.time-label {
  display: block;
  font-size: $text-xs;
  color: rgba(255, 255, 255, 0.72);
  margin-bottom: 6rpx;
}
.time-value {
  font-size: $text-xl;
  font-weight: $fw-bold;
  color: #fff;
  font-variant-numeric: tabular-nums;
  letter-spacing: -0.5rpx;
}
.time-value.hours {
  color: #fde68a;
}
.time-arrow {
  font-size: $text-md;
  color: rgba(255, 255, 255, 0.5);
}

// 按钮区
.actions {
  display: flex;
  flex-direction: column;
  gap: $space-3;
}
.out-btn {
  background: linear-gradient(135deg, $slate-600, $slate-800);
  box-shadow: 0 4rpx 12rpx rgba($slate-700, 0.22);
  &:active {
    background: $slate-900;
  }
}

// 概览
.overview-top {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: $space-4;
}
.overview-top .emp-section-title {
  margin-bottom: 0;
}
.month-pick {
  font-size: $text-sm;
  color: $brand-600;
  padding: 6rpx 18rpx;
  background: $brand-50;
  border-radius: $radius-pill;
  font-weight: $fw-medium;
}

// 记录卡
.section-head {
  font-size: $text-lg;
  font-weight: $fw-bold;
  color: $slate-800;
  margin: $space-5 0 $space-4 4rpx;
  display: flex;
  align-items: center;
  gap: $space-2;
  &::before {
    content: '';
    width: 6rpx;
    height: 28rpx;
    background: $brand-600;
    border-radius: $radius-pill;
  }
}
.record-card {
  padding: $space-5;
  padding-left: 32rpx;
}
.strip-warn::before { background: $warn !important; }
.strip-info::before { background: $info !important; }
.strip-pending::before { background: $warn !important; }
.record-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: $space-4;
}
.record-date-row {
  display: flex;
  align-items: center;
  gap: $space-2;
}
.record-date {
  font-size: $text-md;
  font-weight: $fw-semibold;
  color: $slate-800;
}
.record-weekday {
  font-size: $text-xs;
  color: $slate-400;
}
.record-times {
  display: flex;
  gap: $space-3;
}
.record-time-item {
  flex: 1;
  text-align: center;
  background: $slate-50;
  border-radius: $radius-md;
  padding: $space-3 $space-2;
}
.rt-label {
  display: block;
  font-size: $text-xs;
  color: $slate-400;
  margin-bottom: 6rpx;
}
.rt-value {
  font-size: $text-md;
  font-weight: $fw-semibold;
  color: $slate-800;
  font-variant-numeric: tabular-nums;
}
.rt-value.accent {
  color: $brand-600;
}
.record-remark {
  margin-top: $space-3;
  padding: $space-2 $space-3;
  background: $warn-bg;
  border-radius: $radius-sm;
  font-size: $text-sm;
  color: $warn-deep;
}
</style>
