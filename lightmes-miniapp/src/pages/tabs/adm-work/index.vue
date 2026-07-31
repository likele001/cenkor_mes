<template>
  <view class="adm-page">
    <view class="adm-hero">
      <text class="adm-hero-title">工作台</text>
      <text class="adm-hero-sub">{{ userName }} · {{ today }}</text>
    </view>

    <!-- 顶部统计概览 -->
    <view v-if="canDashboard && !loading" class="adm-stat-grid">
      <view class="adm-stat-card tone-blue">
        <text class="adm-stat-label">待审订单</text>
        <text class="adm-stat-value">{{ summary.orders?.pending_confirm ?? '—' }}</text>
      </view>
      <view class="adm-stat-card tone-green">
        <text class="adm-stat-label">进行中任务</text>
        <text class="adm-stat-value">{{ summary.tasks?.working ?? '—' }}</text>
      </view>
      <view class="adm-stat-card tone-orange">
        <text class="adm-stat-label">待审报工</text>
        <text class="adm-stat-value">{{ summary.reports?.pending_audit ?? '—' }}</text>
      </view>
      <view class="adm-stat-card tone-violet">
        <text class="adm-stat-label">今日报工</text>
        <text class="adm-stat-value">{{ summary.today?.report_count ?? '—' }}</text>
      </view>
    </view>
    <view v-else-if="loading" class="adm-card">
      <text class="adm-empty-tip">加载中...</text>
    </view>

    <!-- 快捷操作 -->
    <view class="adm-card quick-actions">
      <view class="qa-title">快捷操作</view>
      <view class="qa-grid">
        <view class="qa-item" @tap="go('/pages-admin/production/orders/index')">
          <text class="qa-icon">📦</text>
          <text class="qa-text">订单管理</text>
        </view>
        <view class="qa-item" @tap="go('/pages-admin/production/tasks/index')">
          <text class="qa-icon">⚙️</text>
          <text class="qa-text">任务管理</text>
        </view>
        <view class="qa-item" @tap="go('/pages-admin/production/work-orders/index')">
          <text class="qa-icon">📋</text>
          <text class="qa-text">工单管理</text>
        </view>
        <view class="qa-item" @tap="go('/pages-admin/production/trace/index')">
          <text class="qa-icon">🔍</text>
          <text class="qa-text">产品溯源</text>
        </view>
      </view>
    </view>

    <!-- 功能菜单 -->
    <AdminMenuSection
      v-for="group in menuGroups"
      :key="group.key"
      :title="group.title"
      :items="group.items"
      @navigate="navigate"
    />

    <view v-if="!menuGroups.length && !loading" class="adm-empty-tip">暂无可用功能，请联系管理员分配权限</view>
  </view>
</template>

<script setup lang="ts">
import { computed, reactive, ref } from 'vue'
import { onShow } from '@dcloudio/uni-app'
import AdminMenuSection from '@/components/admin-ui/AdminMenuSection.vue'
import { useAdminMenu } from '@/constants/adminMenu'
import { useAuthStore } from '@/stores/auth'
import { PermissionCode } from '@/constants/permissions'
import { adminApi } from '@/api/admin/index'

type Summary = {
  today?: { report_count?: number }
  orders?: { pending_confirm?: number }
  tasks?: { working?: number }
  reports?: { pending_audit?: number }
}

const auth = useAuthStore()
const { menuGroups, navigate } = useAdminMenu()
const loading = ref(false)
const summary = reactive<Summary>({})

const canDashboard = computed(() => auth.hasPermission(PermissionCode.DASHBOARD_VIEW))
const userName = computed(() => auth.userInfo?.full_name || auth.userInfo?.username || '管理员')
const today = computed(() => new Date().toLocaleDateString('zh-CN'))

onShow(() => load())

async function load() {
  if (!canDashboard.value) return
  loading.value = true
  try {
    const d = (await adminApi.dashboardSummary()) as Summary
    Object.assign(summary, d)
  } catch {
    /* ignore */
  } finally {
    loading.value = false
  }
}

function go(url: string) {
  uni.navigateTo({ url })
}
</script>

<style scoped lang="scss">
.quick-actions {
  padding: 24rpx;
}
.qa-title {
  font-size: 28rpx;
  font-weight: 600;
  color: #334155;
  margin-bottom: 16rpx;
}
.qa-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16rpx;
}
.qa-item {
  text-align: center;
  padding: 20rpx 8rpx;
  background: #f8fafc;
  border-radius: 16rpx;
}
.qa-icon {
  font-size: 40rpx;
  display: block;
}
.qa-text {
  display: block;
  margin-top: 8rpx;
  font-size: 22rpx;
  color: #475569;
}
</style>
