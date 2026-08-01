<template>
  <view class="emp-page">
    <view v-if="item" class="emp-card emp-card--striped detail-card" :class="stripClass">
      <view class="detail-head">
        <text class="title">{{ title }}</text>
        <text class="emp-tag" :class="status.tone">{{ status.text }}</text>
      </view>

      <view class="emp-kv-grid body">
        <view class="emp-kv">
          <text class="k">订单号</text>
          <text class="v">{{ orderLabel }}</text>
        </view>
        <view class="emp-kv">
          <text class="k">工序</text>
          <text class="v">{{ item.process?.name || '—' }}</text>
        </view>
        <view class="emp-kv">
          <text class="k">分配数量</text>
          <text class="v">{{ item.assigned_qty ?? 0 }}</text>
        </view>
        <view class="emp-kv">
          <text class="k">已报数量</text>
          <text class="v reported">{{ item.reported_qty ?? 0 }}</text>
        </view>
        <view class="emp-kv">
          <text class="k">剩余数量</text>
          <text class="v highlight">{{ item.remaining_qty ?? 0 }}</text>
        </view>
        <view class="emp-kv">
          <text class="k">任务码</text>
          <text class="v mono">{{ item.task_code }}</text>
        </view>
      </view>

      <view class="emp-progress">
        <view class="emp-progress-bar">
          <view class="emp-progress-fill" :style="{ width: progressWidth }" />
        </view>
        <view class="emp-progress-meta">
          <text>完成进度</text>
          <text class="progress-pct">{{ progressPct }}%</text>
        </view>
      </view>

      <button v-if="canReport" class="emp-btn-primary report-btn" @tap="goReport">开始报工</button>
    </view>

    <!-- 工单信息 -->
    <view v-if="item?.work_order" class="emp-card">
      <text class="emp-section-title">工单信息</text>
      <view class="emp-kv-grid">
        <view class="emp-kv">
          <text class="k">工单数量</text>
          <text class="v">{{ item.work_order.qty ?? '—' }}</text>
        </view>
        <view v-if="item.work_order.order_code" class="emp-kv">
          <text class="k">关联订单</text>
          <text class="v">{{ item.work_order.order_code }}</text>
        </view>
        <view v-if="item.work_order.sku" class="emp-kv">
          <text class="k">产品型号</text>
          <text class="v">{{ skuDisplay(item.work_order.sku) }}</text>
        </view>
        <view v-if="item.work_order.product" class="emp-kv">
          <text class="k">产品</text>
          <text class="v">{{ item.work_order.product.name || item.work_order.product.code }}</text>
        </view>
      </view>
    </view>

    <!-- 最近报工 -->
    <view v-if="recentReports.length" class="emp-card">
      <text class="emp-section-title">最近报工</text>
      <view v-for="r in recentReports" :key="r.id" class="report-item">
        <view class="report-left">
          <text class="report-label">{{ r.sku_label || r.unit_label || r.task_code || `#${r.unit_seq}` }}</text>
          <text class="report-time">{{ formatReportTime(r.submitted_at || r.created_at) }}</text>
        </view>
        <text class="emp-tag" :class="r.result_type === 'bad' ? 'danger' : 'ok'">
          {{ r.result_type === 'bad' ? '不良' : '合格' }}
        </text>
      </view>
    </view>

    <view v-if="loadError" class="emp-empty">
      <text class="emp-empty-icon">!</text>
      {{ loadError }}
    </view>
  </view>
</template>

<script setup lang="ts">
import { onLoad, onPullDownRefresh } from '@dcloudio/uni-app'
import { computed, ref } from 'vue'
import { getTaskDetail, type H5Task, type H5Sku } from '@/api/h5/tasks'
import { getMyReportUnits, type ReportUnitItem } from '@/api/h5/reportUnits'
import { taskStatusLabel } from '@/utils/statusLabels'
import { taskOrderLabel, taskSkuTitle } from '@/utils/taskDisplay'

const item = ref<H5Task | null>(null)
const recentReports = ref<ReportUnitItem[]>([])
const loadError = ref('')
const loading = ref(false)
const taskCode = ref('')

const title = computed(() => (item.value ? taskSkuTitle(item.value) : ''))
const orderLabel = computed(() => (item.value ? taskOrderLabel(item.value) : '—'))
const status = computed(() => taskStatusLabel(item.value?.status || ''))
const canReport = computed(
  () => item.value && item.value.status !== 'done' && (item.value.remaining_qty ?? 0) > 0,
)
const stripClass = computed(() => {
  const map: Record<string, string> = {
    pending: 'strip-pending',
    working: 'strip-working',
    done: 'strip-done',
  }
  return map[item.value?.status || ''] || 'strip-info'
})
const progressPct = computed(() => {
  if (!item.value) return 0
  const a = Number(item.value.assigned_qty ?? 0)
  const r = Number(item.value.reported_qty ?? 0)
  if (!a) return 0
  return Math.min(100, Math.round((r / a) * 100))
})
const progressWidth = computed(() => `${progressPct.value}%`)

function skuDisplay(sku: H5Sku) {
  return sku.display_label || sku.name || sku.code || '—'
}

function formatReportTime(dt: string | null | undefined) {
  if (!dt) return '—'
  const d = new Date(dt)
  return `${d.getMonth() + 1}/${d.getDate()} ${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`
}

onLoad((q) => {
  if (q?.code) {
    taskCode.value = String(q.code)
    load(taskCode.value)
    loadRecentReports(taskCode.value)
  }
})

async function load(code: string) {
  loading.value = true
  loadError.value = ''
  try {
    item.value = await getTaskDetail(code)
  } catch (e: any) {
    loadError.value = (e?.message) ? String(e.message) : '加载失败'
    uni.showToast({ title: loadError.value, icon: 'none' })
  } finally {
    loading.value = false
  }
}

async function loadRecentReports(taskCode: string) {
  try {
    const r = await getMyReportUnits({ limit: 20 })
    recentReports.value = (r.items || [])
      .filter((i) => i.task_code === taskCode)
      .slice(0, 5)
  } catch {
    recentReports.value = []
  }
}

function goReport() {
  if (!item.value) return
  const url = item.value.use_unit_report
    ? `/pages-employee/report/unit/index?task_code=${encodeURIComponent(item.value.task_code)}`
    : `/pages-employee/report/scan/index?task_code=${encodeURIComponent(item.value.task_code)}`
  uni.navigateTo({ url })
}

onPullDownRefresh(() => {
  load(taskCode.value).finally(() => uni.stopPullDownRefresh())
})
</script>

<style scoped lang="scss">
.detail-card {
  padding: $space-5;
  padding-left: 32rpx;
}
.detail-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: $space-3;
  margin-bottom: $space-4;
}
.title {
  flex: 1;
  font-size: $text-xl;
  font-weight: $fw-bold;
  color: $slate-800;
  line-height: 1.4;
  letter-spacing: -0.3rpx;
}
.body {
  margin-top: $space-4;
}
.mono {
  font-size: $text-xs;
  font-family: monospace;
}
.reported {
  color: $brand-600;
}
.highlight {
  color: $warn-deep;
  font-weight: $fw-bold;
}
.progress-pct {
  color: $brand-600;
  font-weight: $fw-semibold;
}
.report-btn {
  margin-top: $space-5;
}

.report-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: $space-4 0;
  border-bottom: 1rpx solid $slate-100;
  &:last-child { border-bottom: none; }
}
.report-left {
  display: flex;
  flex-direction: column;
  gap: 4rpx;
}
.report-label {
  font-size: $text-base;
  color: $slate-800;
  font-weight: $fw-medium;
}
.report-time {
  font-size: $text-xs;
  color: $slate-400;
}
</style>
