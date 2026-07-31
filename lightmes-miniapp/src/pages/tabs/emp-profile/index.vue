<template>
  <view class="emp-page">
    <view class="emp-card profile-card">
      <view class="profile-row">
        <view class="avatar">{{ avatarText }}</view>
        <view class="profile-info">
          <text class="name">{{ auth.userInfo?.full_name || auth.userInfo?.username }}</text>
          <text class="role">{{ auth.roles.join(' · ') || '员工' }}</text>
        </view>
      </view>
    </view>

    <!-- 统计卡片区 -->
    <view class="emp-card stats-card">
      <view class="stats-title">本月概览</view>
      <view class="emp-stat-grid">
        <view class="stat-item">
          <view class="stat-val">{{ attendanceDays }}</view>
          <view class="stat-lbl">出勤天数</view>
        </view>
        <view class="stat-item">
          <view class="stat-val">{{ totalReports }}</view>
          <view class="stat-lbl">报工件数</view>
        </view>
        <view class="stat-item">
          <view class="stat-val money">¥{{ monthSalary }}</view>
          <view class="stat-lbl">预估工资</view>
        </view>
      </view>
    </view>

    <view class="emp-card menu">
      <view class="row" @tap="go('/pages-employee/salary/index/index')">
        <text>工资统计</text>
        <text class="arrow">›</text>
      </view>
      <view class="row" @tap="go('/pages-employee/salary/slip/index')">
        <text>电子工资条</text>
        <text class="arrow">›</text>
      </view>
      <view class="row" @tap="go('/pages-employee/report/history/index')">
        <text>报工记录</text>
        <text class="arrow">›</text>
      </view>
      <view class="row" @tap="go('/pages-employee/notification/list/index')">
        <text>消息中心</text>
        <text v-if="auth.unreadCount > 0" class="badge">{{ auth.unreadCount }}</text>
        <text v-else class="arrow">›</text>
      </view>
      <view class="row" @tap="go('/pages/shared/help/index')">
        <text>智能帮助</text>
        <text class="arrow">›</text>
      </view>
      <view class="row" @tap="go('/pages/shared/trace/index')">
        <text>产品溯源查询</text>
        <text class="arrow">›</text>
      </view>
      <view class="bind-section">
        <ChannelBindCard ref="channelBindRef" />
      </view>
      <view class="row" @tap="go('/pages/shared/about/index')">
        <text>关于</text>
        <text class="arrow">›</text>
      </view>
      <view class="row danger" @tap="logout">退出登录</view>
    </view>
  </view>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { onShow } from '@dcloudio/uni-app'
import ChannelBindCard from '@/components/shared/ChannelBindCard.vue'
import { useAuthStore } from '@/stores/auth'
import { getDashboardSummary } from '@/api/h5/tasks'
import { getAttendanceRecords } from '@/api/h5/attendance'
import { formatMoney } from '@/utils/taskDisplay'

const channelBindRef = ref<InstanceType<typeof ChannelBindCard> | null>(null)

const auth = useAuthStore()
const attendanceDays = ref(0)
const totalReports = ref(0)
const monthSalary = ref('0.00')

const avatarText = computed(() => {
  const n = auth.userInfo?.full_name || auth.userInfo?.username || '员'
  return n.slice(0, 1).toUpperCase()
})

async function loadStats() {
  try {
    const d = (await getDashboardSummary()) as Record<string, unknown>
    const t = d.today as Record<string, number> | undefined
    totalReports.value = (t?.total_qty ?? t?.good_qty ?? 0)
    monthSalary.value = formatMoney(t?.salary_amount ?? 0)
  } catch { /* ignore */ }
  try {
    const now = new Date()
    const month = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}`
    const r = await getAttendanceRecords({ limit: 60, month })
    attendanceDays.value = (r.items || []).filter((i: any) => i.check_in_at).length
  } catch { /* ignore */ }
}

function go(url: string) {
  uni.navigateTo({ url })
}
function logout() {
  auth.logout()
}

onShow(() => {
  channelBindRef.value?.refresh?.()
  loadStats()
})
</script>

<style scoped lang="scss">
.profile-card {
  padding: 32rpx;
}
.profile-row {
  display: flex;
  align-items: center;
  gap: 24rpx;
}
.avatar {
  width: 96rpx;
  height: 96rpx;
  border-radius: 50%;
  background: #dbeafe;
  color: #2563eb;
  font-size: 40rpx;
  font-weight: 700;
  display: flex;
  align-items: center;
  justify-content: center;
}
.name {
  font-size: 34rpx;
  font-weight: 700;
  display: block;
  color: #1e293b;
}
.profile-info {
  flex: 1;
}
.role {
  margin-top: 8rpx;
  color: #64748b;
  font-size: 24rpx;
  display: block;
}
.stats-card {
  padding: 24rpx;
}
.stats-title {
  font-size: 28rpx;
  font-weight: 600;
  color: #334155;
  margin-bottom: 16rpx;
}
.money {
  font-size: 34rpx;
}
.row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 28rpx 0;
  border-bottom: 1rpx solid #f1f5f9;
  font-size: 28rpx;
  color: #334155;
}
.arrow {
  color: #cbd5e1;
  font-size: 32rpx;
}
.badge {
  background: #ef4444;
  color: #fff;
  font-size: 22rpx;
  padding: 4rpx 12rpx;
  border-radius: 999rpx;
}
.danger {
  color: #ef4444;
  border-bottom: none;
}
.bind-section {
  margin-top: 8rpx;
}
</style>
