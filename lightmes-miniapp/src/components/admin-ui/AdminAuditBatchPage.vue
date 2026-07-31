<template>
  <view class="adm-page">
    <MListLayout :items="items" :loading="loading" empty-text="暂无待审报工" :tap-to-select="false">
      <template #item="{ item }">
        <view class="adm-list-head">
          <text class="adm-list-title">订单：{{ orderCode(item) }}</text>
          <text class="adm-list-badge" :class="reportStatusTone(item.status)">
            {{ reportStatusLabel(item.status) }}
          </text>
        </view>
        <text v-if="taskCode(item)" class="adm-list-subtitle">{{ taskCode(item) }}</text>
        <AdminKvGrid :rows="auditKvRows(item)" />
      </template>
      <template #actions="{ item }">
        <view class="adm-card-btns">
          <button class="adm-card-btn success" @tap="quickApprove(item)">通过</button>
          <button class="adm-card-btn danger" @tap="quickReject(item)">拒绝</button>
          <button class="adm-card-btn primary" @tap="openDetail(item)">详情</button>
        </view>
      </template>
    </MListLayout>
  </view>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { onShow } from '@dcloudio/uni-app'
import AdminKvGrid from '@/components/admin-ui/AdminKvGrid.vue'
import MListLayout from '@/components/admin-ui/MListLayout.vue'
import { auditAdminApi, reportStatusLabel, type ReportRow } from '@/api/admin/audit'
import { adminReportStatusTone } from '@/utils/adminStatusLabels'
import { usePermission } from '@/composables/usePermission'
import { formatDateTime } from '@/utils/taskDisplay'

const reportStatusTone = adminReportStatusTone
const { requirePermission } = usePermission()
const items = ref<ReportRow[]>([])
const loading = ref(false)

onShow(async () => {
  if (!requirePermission('report.audit')) return
  await reload()
})

function userLabel(item: ReportRow) {
  return item.report_user?.full_name || item.report_user?.username || '—'
}

function orderCode(item: ReportRow) {
  const row = item as ReportRow & { order_code?: string; task?: { order_code?: string } }
  return row.order_code || row.task?.order_code || `报工#${item.id}`
}

function taskCode(item: ReportRow) {
  return item.task?.task_code || ''
}

function auditKvRows(item: ReportRow) {
  const wage = (item as ReportRow & { wage_amount?: number }).wage_amount
  return [
    { label: '任务', value: item.task?.task_code || `任务#${item.task_id}` },
    { label: '员工', value: userLabel(item) },
    { label: '数量', value: `良${item.good_qty} / 不良${item.bad_qty}` },
    { label: '总工资', value: wage != null ? `¥${wage}` : '—' },
    { label: '时间', value: formatDateTime(item.created_at) },
  ]
}

async function reload() {
  loading.value = true
  try {
    const r = await auditAdminApi.listReports({ limit: 50, pending_audit: true })
    items.value = r.items || []
  } catch {
    items.value = []
  } finally {
    loading.value = false
  }
}

function openDetail(row: ReportRow) {
  uni.navigateTo({ url: `/pages-admin/audit/detail/index?id=${row.id}&type=batch` })
}

async function quickApprove(row: ReportRow) {
  try {
    if (row.status === 'submitted') {
      await auditAdminApi.leaderApproveReport(row.id)
    } else if (row.status === 'leader_approved') {
      await auditAdminApi.qcApproveReport(row.id)
    } else {
      uni.showToast({ title: '当前状态不可审核', icon: 'none' })
      return
    }
    uni.showToast({ title: '已通过', icon: 'success' })
    await reload()
  } catch {
    uni.showToast({ title: '操作失败', icon: 'none' })
  }
}

function quickReject(row: ReportRow) {
  uni.showModal({
    title: '拒绝报工',
    editable: true,
    placeholderText: '请输入驳回原因',
    success: async (res) => {
      if (!res.confirm) return
      try {
        await auditAdminApi.rejectReport(row.id, res.content || '驳回')
        uni.showToast({ title: '已拒绝', icon: 'success' })
        await reload()
      } catch {
        uni.showToast({ title: '操作失败', icon: 'none' })
      }
    },
  })
}
</script>
