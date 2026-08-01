<template>
  <view class="emp-page">
    <!-- 渐变个人卡 -->
    <view class="emp-card emp-card--brand profile-card">
      <view class="profile-row">
        <view class="avatar">{{ avatarText }}</view>
        <view class="profile-info">
          <text class="name">{{ auth.userInfo?.full_name || auth.userInfo?.username }}</text>
          <text class="role">{{ auth.roles.join(' · ') || '员工' }}</text>
        </view>
      </view>

      <view class="hero-stats">
        <view class="stat-item">
          <view class="stat-val">{{ attendanceDays }}</view>
          <view class="stat-lbl">本月出勤</view>
        </view>
        <view class="stat-divider" />
        <view class="stat-item">
          <view class="stat-val">{{ totalReports }}</view>
          <view class="stat-lbl">报工件数</view>
        </view>
        <view class="stat-divider" />
        <view class="stat-item">
          <view class="stat-val">¥{{ monthSalary }}</view>
          <view class="stat-lbl">预估工资</view>
        </view>
      </view>
    </view>

    <!-- 常用功能 -->
    <view class="section-head">常用功能</view>
    <view class="emp-card menu">
      <view class="emp-row" @tap="go('/pages-employee/salary/index/index')">
        <view class="emp-row-label">
          <view class="emp-row-icon icon-violet">薪</view>
          <text>工资统计</text>
        </view>
        <text class="emp-row-arrow">›</text>
      </view>
      <view class="emp-row" @tap="go('/pages-employee/salary/slip/index')">
        <view class="emp-row-label">
          <view class="emp-row-icon icon-emerald">条</view>
          <text>电子工资条</text>
        </view>
        <text class="emp-row-arrow">›</text>
      </view>
      <view class="emp-row" @tap="go('/pages-employee/report/history/index')">
        <view class="emp-row-label">
          <view class="emp-row-icon icon-blue">录</view>
          <text>报工记录</text>
        </view>
        <text class="emp-row-arrow">›</text>
      </view>
      <view class="emp-row" @tap="go('/pages-employee/notification/list/index')">
        <view class="emp-row-label">
          <view class="emp-row-icon icon-rose">消</view>
          <text>消息中心</text>
        </view>
        <text v-if="auth.unreadCount > 0" class="emp-row-badge">{{ auth.unreadCount }}</text>
        <text v-else class="emp-row-arrow">›</text>
      </view>
    </view>

    <!-- 其他服务 -->
    <view class="section-head">其他服务</view>
    <view class="emp-card menu">
      <view class="emp-row" @tap="go('/pages/shared/help/index')">
        <view class="emp-row-label">
          <view class="emp-row-icon icon-amber">助</view>
          <text>智能帮助</text>
        </view>
        <text class="emp-row-arrow">›</text>
      </view>
      <view class="emp-row" @tap="go('/pages/shared/trace/index')">
        <view class="emp-row-label">
          <view class="emp-row-icon icon-slate">溯</view>
          <text>产品溯源查询</text>
        </view>
        <text class="emp-row-arrow">›</text>
      </view>
      <view class="bind-section">
        <ChannelBindCard ref="channelBindRef" />
      </view>
      <view class="emp-row" @tap="go('/pages/shared/about/index')">
        <view class="emp-row-label">
          <view class="emp-row-icon icon-slate">于</view>
          <text>关于</text>
        </view>
        <text class="emp-row-arrow">›</text>
      </view>
      <view class="emp-row danger-row" @tap="logout">
        <view class="emp-row-label">
          <view class="emp-row-icon icon-danger">退</view>
          <text class="danger-text">退出登录</text>
        </view>
      </view>
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
// 个人卡
.profile-card {
  padding: $space-6;
  border-radius: $radius-xl;
}
.profile-row {
  display: flex;
  align-items: center;
  gap: $space-4;
  margin-bottom: $space-6;
}
.avatar {
  width: 104rpx;
  height: 104rpx;
  border-radius: $radius-xl;
  background: rgba(255, 255, 255, 0.22);
  backdrop-filter: blur(8rpx);
  border: 2rpx solid rgba(255, 255, 255, 0.35);
  color: #fff;
  font-size: $text-2xl;
  font-weight: $fw-bold;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.profile-info {
  flex: 1;
  min-width: 0;
}
.name {
  font-size: $text-xl;
  font-weight: $fw-bold;
  color: #fff;
  display: block;
  letter-spacing: -0.3rpx;
}
.role {
  margin-top: 6rpx;
  color: rgba(255, 255, 255, 0.82);
  font-size: $text-sm;
  display: block;
}

// 渐变卡内的统计
.hero-stats {
  display: flex;
  align-items: center;
  background: rgba(255, 255, 255, 0.12);
  border-radius: $radius-lg;
  padding: $space-5 $space-3;
  backdrop-filter: blur(8rpx);
}
.hero-stats .stat-item {
  flex: 1;
  text-align: center;
}
.hero-stats .stat-val {
  font-size: $text-xl;
  font-weight: $fw-bold;
  color: #fff;
  line-height: 1.1;
  font-variant-numeric: tabular-nums;
  letter-spacing: -0.5rpx;
}
.hero-stats .stat-lbl {
  margin-top: $space-1;
  font-size: $text-xs;
  color: rgba(255, 255, 255, 0.78);
}
.stat-divider {
  width: 1rpx;
  height: 56rpx;
  background: rgba(255, 255, 255, 0.2);
}

// 区块标题
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

// 菜单
.menu {
  padding: 0 $space-6;
}
.emp-row {
  padding: $space-5 0;
}
.emp-row-icon {
  width: 56rpx;
  height: 56rpx;
  border-radius: $radius-md;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: $text-sm;
  font-weight: $fw-bold;
}
.icon-blue    { background: $brand-50;  color: $brand-600; }
.icon-amber   { background: $warn-bg;   color: $warn-deep; }
.icon-emerald { background: $success-bg; color: $success-deep; }
.icon-violet  { background: #ede9fe;    color: #6d28d9; }
.icon-rose    { background: $danger-bg; color: $danger-deep; }
.icon-slate   { background: $slate-100; color: $slate-700; }
.icon-danger  { background: $danger-bg; color: $danger-deep; }

.danger-row {
  .danger-text {
    color: $danger;
    font-weight: $fw-medium;
  }
}

.bind-section {
  border-bottom: 1rpx solid $slate-100;
}
</style>
