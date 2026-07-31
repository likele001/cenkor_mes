<template>
  <view class="adm-page">
    <view class="adm-hero">
      <text class="adm-hero-title">报工审核</text>
      <text class="adm-hero-sub">待审 {{ pending }} 条 · 班长初审 / 质检终审</text>
      <view v-if="prescreenStats.total" class="prescreen-stats">
        <text v-if="prescreenStats.red" class="ps red">高风险 {{ prescreenStats.red }}</text>
        <text v-if="prescreenStats.yellow" class="ps yellow">关注 {{ prescreenStats.yellow }}</text>
        <text v-if="prescreenStats.green" class="ps green">低风险 {{ prescreenStats.green }}</text>
      </view>
    </view>

    <view v-if="canAiSummary" class="ai-quick">
      <button class="ai-quick-btn" :loading="summaryLoading" @tap="runAuditSummary">AI 批量摘要</button>
    </view>

    <view v-if="!auditItems.length" class="adm-empty-tip">无 report.audit 权限</view>

    <view
      v-for="item in auditItems"
      :key="item.path"
      class="adm-audit-card"
      hover-class="adm-menu-item-hover"
      @tap="navigate(item.path)"
    >
      <view class="adm-audit-icon" :class="item.tone || 'rose'">{{ item.icon }}</view>
      <view class="adm-audit-body">
        <text class="adm-audit-title">{{ item.title }}</text>
        <text class="adm-audit-desc">{{ item.path.includes('unit') ? '逐件扫码报工 · 件次审核' : '批量报工 · 历史审核列表' }}</text>
      </view>
      <text class="adm-list-arrow">›</text>
    </view>

    <view v-if="summaryVisible" class="mask" @tap="summaryVisible = false">
      <view class="sheet" @tap.stop>
        <view class="head"><text class="title">待审 AI 批量摘要</text></view>
        <scroll-view scroll-y class="body">
          <view v-if="summaryData">
            <text v-if="summaryData.pending_count != null" class="meta">待审 {{ summaryData.pending_count }} 条</text>
            <text v-if="summaryData.summary" class="summary-text">{{ summaryData.summary }}</text>
            <text v-if="summaryData.high_risk_ids?.length" class="section-title">高风险件次 ID</text>
            <text v-if="summaryData.high_risk_ids?.length" class="summary-text">{{ summaryData.high_risk_ids.join(', ') }}</text>
            <text v-if="summaryData.risk_points?.length" class="section-title">风险点</text>
            <text v-for="(p, i) in summaryData.risk_points" :key="'r' + i" class="bullet">· {{ p }}</text>
            <text v-if="summaryData.suggest_actions?.length" class="section-title">建议动作</text>
            <text v-for="(a, i) in summaryData.suggest_actions" :key="'a' + i" class="bullet">· {{ a }}</text>
          </view>
          <text v-else class="summary-text">{{ summaryLoading ? '生成中…' : '暂无摘要' }}</text>
        </scroll-view>
        <button class="close-btn" @tap="summaryVisible = false">关闭</button>
      </view>
    </view>
  </view>
</template>

<script setup lang="ts">
import { computed, reactive, ref } from 'vue'
import { onShow } from '@dcloudio/uni-app'
import { adminApi } from '@/api/admin/index'
import { aiAdminApi } from '@/api/admin/ai'
import { auditAdminApi } from '@/api/admin/audit'
import { useAdminMenu } from '@/constants/adminMenu'
import { useAuthStore } from '@/stores/auth'
import { PermissionCode } from '@/constants/permissions'

const auth = useAuthStore()
const { auditItems, navigate, canDashboard } = useAdminMenu()
const pending = ref(0)
const summaryLoading = ref(false)
const summaryVisible = ref(false)
const summaryData = ref<Record<string, unknown> | null>(null)
const prescreenStats = reactive({ total: 0, green: 0, yellow: 0, red: 0 })

const canAiSummary = computed(
  () => auth.hasPermission(PermissionCode.AI_USE) && auth.hasPermission(PermissionCode.REPORT_AUDIT),
)

async function runAuditSummary() {
  summaryLoading.value = true
  summaryVisible.value = true
  summaryData.value = null
  try {
    summaryData.value = (await aiAdminApi.auditSummary('submitted')) as Record<string, unknown>
  } catch (e: unknown) {
    summaryData.value = { summary: (e as Error).message || 'AI 暂不可用' }
  } finally {
    summaryLoading.value = false
  }
}

onShow(async () => {
  if (!canDashboard.value) return
  try {
    const d = (await adminApi.dashboardSummary()) as { reports?: { pending_audit?: number } }
    pending.value = d.reports?.pending_audit ?? 0
  } catch {
    pending.value = 0
  }
  if (auth.hasPermission(PermissionCode.REPORT_AUDIT)) {
    try {
      const r = await auditAdminApi.listReportUnits({ limit: 100, status: 'submitted' })
      const items = r.items || []
      prescreenStats.green = items.filter((x) => x.prescreen_level === 'green').length
      prescreenStats.yellow = items.filter((x) => x.prescreen_level === 'yellow').length
      prescreenStats.red = items.filter((x) => x.prescreen_level === 'red').length
      prescreenStats.total = prescreenStats.green + prescreenStats.yellow + prescreenStats.red
    } catch {
      prescreenStats.total = 0
      prescreenStats.green = 0
      prescreenStats.yellow = 0
      prescreenStats.red = 0
    }
  }
})
</script>

<style scoped>
.adm-audit-icon.rose { background: #fff1f2; }
.adm-audit-icon.violet { background: #f5f3ff; }
.prescreen-stats { display: flex; flex-wrap: wrap; gap: 12rpx; margin-top: 12rpx; }
.ps { font-size: 22rpx; padding: 4rpx 14rpx; border-radius: 999rpx; }
.ps.green { background: #dcfce7; color: #15803d; }
.ps.yellow { background: #fef3c7; color: #b45309; }
.ps.red { background: #fee2e2; color: #b91c1c; }
.ai-quick { padding: 0 24rpx 16rpx; }
.ai-quick-btn {
  font-size: 26rpx;
  background: #fffbeb;
  color: #b45309;
  border: 1rpx solid #fcd34d;
  border-radius: 12rpx;
  padding: 12rpx 24rpx;
}
.mask { position: fixed; inset: 0; background: rgba(15,23,42,.45); z-index: 9999; display: flex; align-items: flex-end; }
.sheet { width: 100%; max-height: 70vh; background: #fff; border-radius: 24rpx 24rpx 0 0; padding-bottom: env(safe-area-inset-bottom); }
.head { padding: 28rpx 32rpx; border-bottom: 1rpx solid #f1f5f9; }
.title { font-size: 32rpx; font-weight: 700; }
.body { max-height: 50vh; padding: 24rpx 32rpx; }
.summary-text { font-size: 26rpx; color: #334155; white-space: pre-wrap; line-height: 1.6; }
.meta { display: block; font-size: 22rpx; color: #94a3b8; margin-bottom: 12rpx; }
.section-title { display: block; font-size: 26rpx; font-weight: 600; color: #b45309; margin: 16rpx 0 8rpx; }
.bullet { display: block; font-size: 26rpx; color: #334155; line-height: 1.5; margin-bottom: 6rpx; }
.close-btn { margin: 16rpx 32rpx 24rpx; background: #f1f5f9; color: #475569; border-radius: 12rpx; font-size: 28rpx; }
</style>
