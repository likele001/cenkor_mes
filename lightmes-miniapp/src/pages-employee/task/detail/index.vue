<template>
  <view class="emp-page">
    <view v-if="item" class="emp-card">
      <text class="title">{{ title }}</text>
      <text class="emp-tag" :class="status.tone">{{ status.text }}</text>

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
          <text class="v">{{ item.reported_qty ?? 0 }}</text>
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
          <text>进度</text>
          <text>{{ item.reported_qty ?? 0 }} / {{ item.assigned_qty ?? 0 }}</text>
        </view>
      </view>

      <button v-if="canReport" class="emp-btn-primary" @tap="goReport">开始报工</button>
    </view>

    <!-- 工单信息区块 -->
    <view v-if="item?.work_order" class="emp-card wo-card">
      <text class="section-title">工单信息</text>
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

    <!-- 最近报工记录 -->
    <view v-if="recentReports.length" class="emp-card reports-card">
      <text class="section-title">最近报工</text>
      <view v-for="r in recentReports" :key="r.id" class="report-item">
        <view class="report-left">
          <text class="report-label">{{ r.sku_label || r.unit_label || r.task_code || `#${r.unit_seq}` }}</text>
          <text class="report-time">{{ formatReportTime(r.submitted_at || r.created_at) }}</text>
        </view>
        <text class="report-tag" :class="r.result_type === 'bad' ? 'bad' : 'good'">
          {{ r.result_type === 'bad' ? '不良' : '合格' }}
        </text>
      </view>
    </view>
  </view>
</template>

<script setup lang="ts">
import { onLoad } from '@dcloudio/uni-app'
import { onPullDownRefresh } from '@dcloudio/uni-app'
import { computed, ref } from 'vue'
import { getTaskDetail, type H5Task, type H5Sku } from '@/api/h5/tasks'
import { getMyReportUnits, type ReportUnitItem } from '@/api/h5/reportUnits'
import { taskStatusLabel } from '@/utils/statusLabels'
import { taskOrderLabel, taskSkuTitle } from '@/utils/taskDisplay'

const item = ref<H5Task | null>(null)
const recentReports = ref<ReportUnitItem[]>([])

const title = computed(() => (item.value ? taskSkuTitle(item.value) : ''))
const orderLabel = computed(() => (item.value ? taskOrderLabel(item.value) : '—'))
const status = computed(() => taskStatusLabel(item.value?.status || ''))
const canReport = computed(
  () => item.value && item.value.status !== 'done' && (item.value.remaining_qty ?? 0) > 0,
)
const progressWidth = computed(() => {
  if (!item.value) return '0%'
  const a = Number(item.value.assigned_qty ?? 0)
  const r = Number(item.value.reported_qty ?? 0)
  if (!a) return '0%'
  return `${Math.min(100, Math.round((r / a) * 100))}%`
})

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
    load(String(q.code))
    loadRecentReports(String(q.code))
  }
})

const loadError = ref('')
const loading = ref(false)

async function load(code: string) {
  loading.value = true
  loadError.value = ''
  try {
    item.value = await getTaskDetail(code)
  } catch (e: any) {
    loadError.value = (e?.message) ? String(e.message) :  加载失败
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
.title {
  font-size: 34rpx;
  font-weight: 700;
  color: #1e293b;
  display: block;
  margin-bottom: 12rpx;
}
.body {
  margin-top: 24rpx;
}
.mono {
  font-size: 22rpx;
}
.highlight {
  color: #2563eb;
  font-weight: 600;
}
.emp-btn-primary {
  margin-top: 32rpx;
}
.wo-card {
  padding: 24rpx;
}
.section-title {
  display: block;
  font-size: 28rpx;
  font-weight: 600;
  color: #334155;
  margin-bottom: 16rpx;
}
.reports-card {
  padding: 24rpx;
}
.report-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16rpx 0;
  border-bottom: 1rpx solid #f1f5f9;
}
.report-item:last-child {
  border-bottom: none;
}
.report-left {
  display: flex;
  flex-direction: column;
  gap: 6rpx;
}
.report-label {
  font-size: 26rpx;
  color: #1e293b;
}
.report-time {
  font-size: 22rpx;
  color: #94a3b8;
}
.report-tag {
  font-size: 22rpx;
  padding: 4rpx 14rpx;
  border-radius: 999rpx;
}
.report-tag.good {
  background: #dcfce7;
  color: #15803d;
}
.report-tag.bad {
  background: #fee2e2;
  color: #b91c1c;
}
</style>
