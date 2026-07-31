<template>
  <view class="adm-page">
    <view v-if="loading" class="loading">加载中...</view>
    <view v-else-if="detail" class="adm-card">
      <text class="title">报工 #{{ detail.id }}</text>
      <text class="sub">{{ reportStatusLabel(String(detail.status)) }}</text>
      <view class="kv"><text class="k">任务</text><text class="v">{{ taskLabel }}</text></view>
      <view class="kv"><text class="k">报工人</text><text class="v">{{ userLabel }}</text></view>
      <view class="kv"><text class="k">良品</text><text class="v">{{ detail.good_qty }}</text></view>
      <view class="kv"><text class="k">不良</text><text class="v">{{ detail.bad_qty }}</text></view>
      <view class="kv"><text class="k">备注</text><text class="v">{{ detail.remark || '—' }}</text></view>
      <view v-if="hasPerm && canAudit" class="actions">
        <button type="primary" size="mini" @tap="approve('leader')">班长通过</button>
        <button type="primary" size="mini" @tap="approve('qc')">质检通过</button>
        <button size="mini" @tap="reject">驳回</button>
      </view>
    </view>
    <view v-else class="loading">未找到报工记录</view>
  </view>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { onLoad } from '@dcloudio/uni-app'
import { auditAdminApi, reportStatusLabel, type ReportRow } from '@/api/admin/audit'
import { usePermission } from '@/composables/usePermission'
import { PermissionCode } from '@/constants/permissions'

const detail = ref<(ReportRow & Record<string, unknown>) | null>(null)
const loading = ref(true)
const id = ref(0)
const { hasPermission } = usePermission()
const hasPerm = ref(false)

const userLabel = computed(() => {
  const u = detail.value?.report_user
  return u?.full_name || u?.username || '—'
})
const taskLabel = computed(() => detail.value?.task?.task_code || (detail.value?.task_id ? `任务#${detail.value.task_id}` : '—'))
const canAudit = computed(() => ['submitted', 'leader_approved'].includes(String(detail.value?.status)))

onLoad((q) => {
  hasPerm.value = hasPermission(PermissionCode.REPORT_AUDIT)
  id.value = Number(q?.id || 0)
  load()
})

async function load() {
  if (!id.value) {
    loading.value = false
    return
  }
  loading.value = true
  try {
    detail.value = await auditAdminApi.getReport(id.value)
  } catch {
    detail.value = null
  } finally {
    loading.value = false
  }
}

async function approve(type: 'leader' | 'qc') {
  try {
    if (type === 'leader') await auditAdminApi.leaderApproveReport(id.value)
    else await auditAdminApi.qcApproveReport(id.value)
    uni.showToast({ title: '已通过', icon: 'success' })
    await load()
  } catch {
    uni.showToast({ title: '操作失败', icon: 'none' })
  }
}

function reject() {
  uni.showModal({
    title: '驳回',
    editable: true,
    placeholderText: '请输入驳回原因',
    success: async (r) => {
      if (r.confirm && r.content) {
        try {
          await auditAdminApi.rejectReport(id.value, r.content)
          uni.showToast({ title: '已驳回', icon: 'none' })
          await load()
        } catch {
          uni.showToast({ title: '操作失败', icon: 'none' })
        }
      }
    },
  })
}
</script>

<style scoped>
.loading { padding: 40rpx; text-align: center; color: #94a3b8; }
.title { display: block; font-size: 32rpx; font-weight: 700; }
.sub { display: block; font-size: 26rpx; color: #64748b; margin: 12rpx 0 20rpx; }
.kv { display: flex; justify-content: space-between; font-size: 26rpx; padding: 10rpx 0; gap: 16rpx; }
.k { color: #94a3b8; flex-shrink: 0; }
.v { text-align: right; }
.actions {
  display: flex;
  gap: 16rpx;
  margin-top: 24rpx;
  flex-wrap: wrap;
}
</style>
