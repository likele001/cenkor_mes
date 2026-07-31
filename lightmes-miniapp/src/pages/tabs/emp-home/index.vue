<template>
  <view class="emp-page">
    <!-- 自动派工提醒横幅 -->
    <view v-if="newTaskCount > 0" class="emp-card dispatch-banner" @tap="goNewTasks">
      <view class="dispatch-row">
        <text class="dispatch-icon">⚡</text>
        <text class="dispatch-text">系统已自动分配 <text class="dispatch-num">{{ newTaskCount }}</text> 个新任务</text>
        <text class="dispatch-link">查看 ›</text>
      </view>
    </view>

    <view class="emp-card profile-card">
      <view class="profile-row">
        <view class="avatar">{{ avatarText }}</view>
        <view class="profile-info">
          <view class="name-row">
            <text class="name">{{ userName }}</text>
            <text class="online">在线</text>
          </view>
          <text v-if="roleLabel" class="dept">{{ roleLabel }}</text>
        </view>
      </view>
    </view>

    <view class="section-head">今日概览</view>
    <view class="emp-stat-grid">
      <view class="stat-item">
        <view class="stat-val">{{ totalTasks }}</view>
        <view class="stat-lbl">今日任务</view>
      </view>
      <view class="stat-item">
        <view class="stat-val">{{ todayReport }}</view>
        <view class="stat-lbl">今日报工</view>
      </view>
      <view class="stat-item">
        <view class="stat-val money">¥{{ todaySalary }}</view>
        <view class="stat-lbl">今日工资</view>
      </view>
    </view>

    <view class="menu-grid">
      <view class="menu-item" @tap="goTasks">
        <text class="menu-icon">📋</text>
        <text class="menu-text">我的任务</text>
      </view>
      <view class="menu-item" @tap="goScan">
        <text class="menu-icon">📷</text>
        <text class="menu-text">扫码报工</text>
      </view>
      <view class="menu-item" @tap="go('/pages-employee/report/history/index')">
        <text class="menu-icon">📊</text>
        <text class="menu-text">报工记录</text>
      </view>
      <view class="menu-item" @tap="go('/pages-employee/salary/index/index')">
        <text class="menu-icon">💰</text>
        <text class="menu-text">工资统计</text>
      </view>
      <view class="menu-item" @tap="go('/pages-employee/notification/list/index')">
        <text class="menu-icon">🔔</text>
        <text class="menu-text">
          消息中心
          <text v-if="unread > 0" class="menu-badge">{{ unread }}</text>
        </text>
      </view>
    </view>
  </view>
</template>

<script setup lang="ts">
import { onShow } from '@dcloudio/uni-app'
import { computed, ref } from 'vue'
import { getDashboardSummary } from '@/api/h5/tasks'
import { useAuthStore } from '@/stores/auth'
import { formatMoney } from '@/utils/taskDisplay'
import { smartAutoSubscribe } from '@/utils/subscribe'
import { updateTabBarBadge } from '@/mixins/tabBar'

const DISPATCH_KEY = 'emp_home:last_task_total'

const auth = useAuthStore()
const totalTasks = ref(0)
const todayReport = ref(0)
const todaySalary = ref('0.00')
const newTaskCount = ref(0)
const unread = computed(() => auth.unreadCount)
const userName = computed(() => auth.userInfo?.full_name || auth.userInfo?.username || '员工')
const roleLabel = computed(() => auth.roles[0] || '')
const avatarText = computed(() => (userName.value.slice(0, 1) || '员').toUpperCase())

onShow(async () => {
  await auth.refreshUnread()
  updateTabBarBadge(auth.unreadCount)
  load()
  // 智能订阅推送（仅员工端且已绑定 openid 时）
  if (auth.isEmployee) {
    smartAutoSubscribe('emp-home', [
      'dispatch.assigned',
      'report.leader_approved',
      'report.rejected',
      'report.qc_approved',
      'salary.slip_remind',
    ]).catch(() => {})
  }
})

async function load() {
  try {
    const d = (await getDashboardSummary()) as Record<string, unknown>
    const t = d.today as Record<string, number> | undefined
    const tasks = d.my_tasks as Record<string, number> | undefined
    const currentTotal = tasks?.total ?? 0
    totalTasks.value = currentTotal
    todayReport.value = t?.total_qty ?? t?.good_qty ?? 0
    todaySalary.value = formatMoney(t?.salary_amount ?? 0)

    // 检测自动派工新任务
    const lastTotal = Number(uni.getStorageSync(DISPATCH_KEY) || 0)
    if (lastTotal > 0 && currentTotal > lastTotal) {
      newTaskCount.value = currentTotal - lastTotal
    }
    uni.setStorageSync(DISPATCH_KEY, currentTotal)
  } catch {
    /* ignore */
  }
}

function goNewTasks() {
  newTaskCount.value = 0
  goTasks()
}

function go(url: string) {
  uni.navigateTo({ url })
}
function goTasks() {
  uni.switchTab({ url: '/pages/tabs/emp-tasks/index' })
}
function goScan() {
  uni.switchTab({ url: '/pages/tabs/emp-report/index' })
}
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
.name-row {
  display: flex;
  align-items: center;
  gap: 12rpx;
}
.name {
  font-size: 34rpx;
  font-weight: 700;
  color: #1e293b;
}
.online {
  font-size: 20rpx;
  color: #15803d;
  background: #dcfce7;
  padding: 4rpx 12rpx;
  border-radius: 999rpx;
}
.dept {
  margin-top: 8rpx;
  font-size: 24rpx;
  color: #64748b;
}
.section-head {
  font-size: 30rpx;
  font-weight: 700;
  color: #334155;
  margin: 8rpx 0 16rpx 4rpx;
}
.money {
  font-size: 36rpx;
}
.menu-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 20rpx;
  margin-top: 24rpx;
}
.menu-item {
  background: #fff;
  border-radius: 20rpx;
  padding: 36rpx 24rpx;
  text-align: center;
  border: 1rpx solid #eef2f7;
  box-shadow: 0 2rpx 12rpx rgba(15, 23, 42, 0.04);
}
.menu-icon {
  font-size: 48rpx;
  display: block;
}
.menu-text {
  margin-top: 12rpx;
  font-size: 28rpx;
  font-weight: 600;
  color: #334155;
}
.dispatch-banner {
  background: linear-gradient(135deg, #fef3c7, #fde68a);
  border-left: 6rpx solid #f59e0b;
  padding: 20rpx 24rpx;
  margin-bottom: 20rpx;
  border-radius: 16rpx;
}
.dispatch-row {
  display: flex;
  align-items: center;
  gap: 12rpx;
}
.dispatch-icon {
  font-size: 36rpx;
  flex-shrink: 0;
}
.dispatch-text {
  flex: 1;
  font-size: 26rpx;
  color: #92400e;
  line-height: 1.5;
}
.dispatch-num {
  font-weight: 700;
  color: #b45309;
  font-size: 30rpx;
}
.dispatch-link {
  font-size: 24rpx;
  color: #d97706;
  flex-shrink: 0;
}
.menu-badge {
  display: inline-block;
  background: #ef4444;
  color: #fff;
  font-size: 20rpx;
  padding: 2rpx 12rpx;
  border-radius: 999rpx;
  margin-left: 6rpx;
  vertical-align: middle;
}

</style>
