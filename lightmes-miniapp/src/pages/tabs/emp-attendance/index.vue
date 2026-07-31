<template>
  <view class="emp-page">
    <!-- 今日状态卡 -->
    <view class="emp-card today-card">
      <view class="today-head">
        <text class="today-date">{{ todayStr }}</text>
        <text class="today-weekday">{{ weekdayStr }}</text>
      </view>
      <view class="today-status">
        <view class="status-dot" :class="todayStatusClass" />
        <text class="status-text">{{ todayStatusText }}</text>
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
        <view class="time-block right">
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
      <button class="emp-btn-primary out" :loading="loading" :disabled="!todayIn || !!todayOut" @tap="checkOut">
        {{ todayOut ? '已打卡' : '下班打卡' }}
      </button>
    </view>

    <!-- 月度统计 -->
    <view class="emp-card overview">
      <view class="overview-top">
        <text class="overview-title">月度统计</text>
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
    <view v-if="!records.length && !loading" class="emp-empty">暂无打卡记录</view>
    <view v-for="r in records" :key="r.id" class="emp-card record-card">
      <view class="record-head">
        <view class="record-date-row">
          <text class="record-date">{{ r.work_date }}</text>
          <text class="record-weekday">{{ getWeekday(r.work_date) }}</text>
        </view>
        <text class="record-tag" :class="getRecordTag(r).tone">{{ getRecordTag(r).text }}</text>
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
</script>

<style scoped lang="scss">
.today-card {
  padding: 32rpx;
}
.today-head {
  display: flex;
  align-items: center;
  gap: 16rpx;
  margin-bottom: 16rpx;
}
.today-date {
  font-size: 32rpx;
  font-weight: 700;
  color: #1e293b;
}
.today-weekday {
  font-size: 24rpx;
  color: #64748b;
  background: #f1f5f9;
  padding: 4rpx 16rpx;
  border-radius: 999rpx;
}
.today-status {
  display: flex;
  align-items: center;
  gap: 12rpx;
  margin-bottom: 24rpx;
}
.status-dot {
  width: 16rpx;
  height: 16rpx;
  border-radius: 50%;
  background: #cbd5e1;
}
.status-dot.none { background: #f59e0b; }
.status-dot.working { background: #22c55e; animation: pulse 2s infinite; }
.status-dot.done { background: #3b82f6; }
@keyframes pulse { 0%,100% { opacity: 1; } 50% { opacity: 0.4; } }
.status-text {
  font-size: 28rpx;
  font-weight: 600;
  color: #334155;
}
.today-times {
  display: flex;
  align-items: center;
  gap: 20rpx;
  background: #f8fafc;
  border-radius: 16rpx;
  padding: 24rpx;
}
.time-block {
  flex: 1;
  text-align: center;
}
.time-block.right {
  flex: 0.8;
}
.time-label {
  display: block;
  font-size: 22rpx;
  color: #94a3b8;
  margin-bottom: 8rpx;
}
.time-value {
  font-size: 34rpx;
  font-weight: 700;
  color: #1e293b;
}
.time-value.hours {
  color: #2563eb;
}
.time-arrow {
  font-size: 28rpx;
  color: #cbd5e1;
}
.actions {
  display: flex;
  flex-direction: column;
  gap: 16rpx;
}
.out {
  background: linear-gradient(135deg, #64748b, #334155);
}
.overview {
  padding: 24rpx;
}
.overview-top {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20rpx;
}
.overview-title {
  font-size: 28rpx;
  font-weight: 600;
  color: #334155;
}
.month-pick {
  font-size: 24rpx;
  color: #2563eb;
  padding: 6rpx 16rpx;
  background: #eff6ff;
  border-radius: 999rpx;
}
.section-head {
  font-size: 30rpx;
  font-weight: 700;
  color: #334155;
  margin: 8rpx 0 16rpx 4rpx;
}
.record-card {
  padding: 24rpx;
}
.record-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16rpx;
}
.record-date-row {
  display: flex;
  align-items: center;
  gap: 12rpx;
}
.record-date {
  font-size: 28rpx;
  font-weight: 600;
  color: #1e293b;
}
.record-weekday {
  font-size: 22rpx;
  color: #94a3b8;
}
.record-tag {
  font-size: 22rpx;
  padding: 4rpx 14rpx;
  border-radius: 999rpx;
}
.record-tag.ok { background: #dcfce7; color: #15803d; }
.record-tag.warn { background: #fef3c7; color: #b45309; }
.record-tag.info { background: #dbeafe; color: #2563eb; }
.record-times {
  display: flex;
  gap: 24rpx;
}
.record-time-item {
  flex: 1;
  text-align: center;
  background: #f8fafc;
  border-radius: 12rpx;
  padding: 16rpx 8rpx;
}
.rt-label {
  display: block;
  font-size: 22rpx;
  color: #94a3b8;
  margin-bottom: 6rpx;
}
.rt-value {
  font-size: 28rpx;
  font-weight: 600;
  color: #1e293b;
}
.rt-value.accent {
  color: #2563eb;
}
.record-remark {
  margin-top: 16rpx;
  padding: 12rpx 16rpx;
  background: #f8fafc;
  border-radius: 12rpx;
  font-size: 24rpx;
  color: #64748b;
}
</style>
