<template>
  <view class="emp-page home-page">
    <!-- 顶部品牌区：个人卡 + 今日概览合并 -->
    <view class="hero emp-card--brand">
      <view class="hero-profile">
        <view class="avatar">{{ avatarText }}</view>
        <view class="profile-info">
          <view class="name-row">
            <text class="name">{{ userName }}</text>
            <view v-if="newTaskCount > 0" class="dispatch-pill" @tap="goNewTasks">
              <text class="dispatch-icon">⚡</text>
              <text class="dispatch-text">{{ newTaskCount }} 个新任务</text>
            </view>
          </view>
          <text v-if="roleLabel" class="role">{{ roleLabel }}</text>
        </view>
      </view>

      <view class="hero-stats">
        <view class="stat-item">
          <view class="stat-val">{{ totalTasks }}</view>
          <view class="stat-lbl">今日任务</view>
        </view>
        <view class="stat-divider" />
        <view class="stat-item">
          <view class="stat-val">{{ todayReport }}</view>
          <view class="stat-lbl">今日报工</view>
        </view>
        <view class="stat-divider" />
        <view class="stat-item">
          <view class="stat-val">¥{{ todaySalary }}</view>
          <view class="stat-lbl">今日工资</view>
        </view>
      </view>
    </view>

    <!-- 快捷功能宫格 -->
    <view class="section-head">快捷功能</view>
    <view class="menu-grid">
      <view class="menu-item" @tap="goTasks">
        <view class="menu-icon icon-blue">任</view>
        <text class="menu-text">我的任务</text>
      </view>
      <view class="menu-item" @tap="goScan">
        <view class="menu-icon icon-amber">扫</view>
        <text class="menu-text">扫码报工</text>
      </view>
      <view class="menu-item" @tap="go('/pages-employee/report/history/index')">
        <view class="menu-icon icon-emerald">录</view>
        <text class="menu-text">报工记录</text>
      </view>
      <view class="menu-item" @tap="go('/pages-employee/salary/index/index')">
        <view class="menu-icon icon-violet">薪</view>
        <text class="menu-text">工资统计</text>
      </view>
      <view class="menu-item" @tap="go('/pages-employee/notification/list/index')">
        <view class="menu-icon icon-rose">
          消
          <view v-if="unread > 0" class="menu-badge">{{ unread }}</view>
        </view>
        <text class="menu-text">消息中心</text>
      </view>
      <view class="menu-item" @tap="go('/pages/shared/trace/index')">
        <view class="menu-icon icon-slate">溯</view>
        <text class="menu-text">产品溯源</text>
      </view>
    </view>

    <!-- 待办任务预览 -->
    <view class="section-head-row">
      <text class="section-head-title">待办任务</text>
      <text v-if="pendingTasks.length > 0" class="section-head-link" @tap="goTasks">查看全部 ›</text>
    </view>
    <view v-if="pendingTasks.length === 0" class="emp-empty">
      <text class="emp-empty-icon">✓</text>
      今日任务都已完成
    </view>
    <EmpTaskCard
      v-for="t in pendingTasks.slice(0, 3)"
      :key="t.task_code"
      :task="t"
      @tap="goDetail(t.task_code)"
      @report="goReport(t)"
    />
  </view>
</template>

<script setup lang="ts">
import { onShow } from '@dcloudio/uni-app'
import { computed, ref } from 'vue'
import { getDashboardSummary, getMyTasks, type H5Task } from '@/api/h5/tasks'
import { useAuthStore } from '@/stores/auth'
import { formatMoney } from '@/utils/taskDisplay'
import { smartAutoSubscribe } from '@/utils/subscribe'
import { updateTabBarBadge } from '@/mixins/tabBar'
import EmpTaskCard from '@/components/employee-ui/EmpTaskCard.vue'

const DISPATCH_KEY = 'emp_home:last_task_total'

const auth = useAuthStore()

const totalTasks = ref(0)
const todayReport = ref(0)
const todaySalary = ref('0.00')
const unread = ref(0)
const newTaskCount = ref(0)
const pendingTasks = ref<H5Task[]>([])

const userName = computed(() => auth.userInfo?.full_name || auth.userInfo?.username || '员工')
const roleLabel = computed(() => auth.roles?.join(' · ') || '员工')

const avatarText = computed(() => {
  const n = userName.value
  return n.slice(0, 1).toUpperCase()
})

onShow(() => {
  loadSummary()
  loadTasks()
  smartAutoSubscribe()
})

async function loadSummary() {
  try {
    const d = (await getDashboardSummary()) as Record<string, any>
    const t = d.today || {}
    totalTasks.value = t.total_tasks ?? 0
    todayReport.value = t.total_qty ?? t.good_qty ?? 0
    todaySalary.value = formatMoney(t.salary_amount ?? 0)
    unread.value = d.unread_count ?? 0
    updateTabBarBadge(unread.value)
  } catch { /* ignore */ }
}

async function loadTasks() {
  try {
    const r = await getMyTasks({ limit: 20 })
    const items = r.items || []
    pendingTasks.value = items.filter((t) => t.status === 'pending' || t.status === 'working')

    const last = Number(uni.getStorageSync(DISPATCH_KEY) || 0)
    if (items.length > last) {
      newTaskCount.value = items.length - last
    }
    uni.setStorageSync(DISPATCH_KEY, String(items.length))
  } catch { /* ignore */ }
}

function goTasks() {
  uni.switchTab({ url: '/pages/tabs/emp-tasks/index' })
}

function goScan() {
  uni.switchTab({ url: '/pages/tabs/emp-report/index' })
}

function goNewTasks() {
  newTaskCount.value = 0
  goTasks()
}

function goDetail(code: string) {
  uni.navigateTo({ url: `/pages-employee/task/detail/index?code=${encodeURIComponent(code)}` })
}

function goReport(t: H5Task) {
  const url = t.use_unit_report
    ? `/pages-employee/report/unit/index?task_code=${encodeURIComponent(t.task_code)}`
    : `/pages-employee/report/scan/index?task_code=${encodeURIComponent(t.task_code)}`
  uni.navigateTo({ url })
}

function go(url: string) {
  uni.navigateTo({ url })
}
</script>

<style scoped lang="scss">
// uni.scss 由 uni-app 自动注入，直接用变量

.home-page {
  padding-top: $space-4;
}

// ---- 顶部品牌区 ----
.hero {
  padding: $space-6;
  margin-bottom: $space-6;
  border-radius: $radius-xl;
}

.hero-profile {
  display: flex;
  align-items: center;
  gap: $space-4;
  margin-bottom: $space-6;
}

.avatar {
  width: 96rpx;
  height: 96rpx;
  border-radius: $radius-xl;
  background: rgba(255, 255, 255, 0.22);
  backdrop-filter: blur(8rpx);
  border: 2rpx solid rgba(255, 255, 255, 0.35);
  color: #fff;
  font-size: $text-xl;
  font-weight: $fw-bold;
  display: flex;
  align-items: center;
  justify-content: center;
}

.profile-info {
  flex: 1;
  min-width: 0;
}

.name-row {
  display: flex;
  align-items: center;
  gap: $space-3;
  flex-wrap: wrap;
}

.name {
  font-size: $text-xl;
  font-weight: $fw-bold;
  color: #fff;
  letter-spacing: -0.5rpx;
}

.dispatch-pill {
  display: inline-flex;
  align-items: center;
  gap: 6rpx;
  background: rgba(255, 255, 255, 0.22);
  border: 1rpx solid rgba(255, 255, 255, 0.35);
  padding: 4rpx 14rpx;
  border-radius: $radius-pill;
  font-size: $text-xs;
  color: #fff;
  font-weight: $fw-semibold;
}

.dispatch-icon {
  font-size: $text-sm;
}

.role {
  margin-top: 6rpx;
  color: rgba(255, 255, 255, 0.82);
  font-size: $text-sm;
  display: block;
}

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
  font-size: $text-2xl;
  font-weight: $fw-bold;
  color: #fff;
  line-height: 1.1;
  letter-spacing: -1rpx;
  font-variant-numeric: tabular-nums;
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

// ---- 区块标题 ----
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

.section-head-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin: $space-6 0 $space-4 4rpx;
}

.section-head-title {
  font-size: $text-lg;
  font-weight: $fw-bold;
  color: $slate-800;
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

.section-head-link {
  font-size: $text-sm;
  color: $brand-600;
  font-weight: $fw-medium;
  padding: $space-1 $space-2;
}

// ---- 功能宫格 ----
.menu-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: $space-4;
  margin-bottom: $space-5;
}

.menu-item {
  text-align: center;
  transition: transform $dur-fast $ease-smooth;
  &:active { transform: scale(0.94); }
}

.menu-icon {
  width: 96rpx;
  height: 96rpx;
  border-radius: $radius-lg;
  margin: 0 auto $space-2;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 32rpx;
  font-weight: $fw-bold;
  position: relative;
}

.icon-blue    { background: $brand-50;  color: $brand-600; }
.icon-amber   { background: $warn-bg;   color: $warn-deep; }
.icon-emerald { background: $success-bg; color: $success-deep; }
.icon-violet  { background: #ede9fe;    color: #6d28d9; }
.icon-rose    { background: $danger-bg; color: $danger-deep; }
.icon-slate   { background: $slate-100; color: $slate-700; }

.menu-badge {
  position: absolute;
  top: -6rpx;
  right: -6rpx;
  background: $danger;
  color: #fff;
  font-size: 20rpx;
  font-weight: $fw-bold;
  padding: 2rpx 8rpx;
  min-width: 28rpx;
  height: 28rpx;
  line-height: 24rpx;
  border-radius: $radius-pill;
  border: 2rpx solid #fff;
  box-sizing: border-box;
}

.menu-text {
  font-size: $text-sm;
  color: $slate-700;
  font-weight: $fw-medium;
}
</style>
