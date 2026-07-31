<template>
  <view class="adm-page">
    <view class="toolbar">
      <input v-model="keyword" class="search" placeholder="订单号/任务码" @confirm="reload" />
      <button class="refresh" size="mini" @tap="reload">刷新</button>
    </view>

    <MListLayout :items="items" :loading="loading" empty-text="暂无派工记录" :tap-to-select="false">
      <template #item="{ item }">
        <view class="adm-list-head">
          <text class="adm-list-title">{{ item.task_code }}</text>
          <text class="adm-list-badge tone-active">{{ item.process_name || '工序' }}</text>
        </view>
        <AdminKvGrid :rows="[
          { label: '订单', value: item.order_code || '—' },
          { label: '员工', value: item.user_full_name || item.username || '—' },
          { label: '派工/已报', value: `${item.assigned_qty}/${item.reported_qty ?? 0}` },
        ]" />
      </template>
      <template #actions="{ item }">
        <view class="adm-card-btns">
          <button class="adm-card-btn primary" @tap="openQr(item)">报工码</button>
        </view>
      </template>
    </MListLayout>

    <view v-if="qrVisible" class="mask" @tap="qrVisible = false">
      <view class="sheet" @tap.stop>
        <view class="head"><text class="title">报工码</text></view>
        <scroll-view scroll-y class="body">
          <view class="kv"><text class="k">员工</text><text class="v">{{ qrUser }}</text></view>
          <view class="kv"><text class="k">任务码</text><text class="v mono">{{ qrTaskCode }}</text></view>
          <view class="kv col">
            <text class="k">报工链接</text>
            <text class="v link">{{ qrUrl }}</text>
          </view>
          <view class="hint">员工可扫 H5 报工链接，或在「我的任务」中查看报工码</view>
        </scroll-view>
        <view class="foot">
          <button class="btn ghost" @tap="copyText(qrTaskCode)">复制任务码</button>
          <button class="btn primary" @tap="copyText(qrUrl)">复制链接</button>
        </view>
      </view>
    </view>
  </view>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { onShow } from '@dcloudio/uni-app'
import AdminKvGrid from '@/components/admin-ui/AdminKvGrid.vue'
import MListLayout from '@/components/admin-ui/MListLayout.vue'
import { productionAdminApi, type DispatchAssignment } from '@/api/admin/production'
import { usePermission } from '@/composables/usePermission'

const { requirePermission } = usePermission()
const items = ref<DispatchAssignment[]>([])
const loading = ref(false)
const keyword = ref('')
const qrVisible = ref(false)
const qrTaskCode = ref('')
const qrUrl = ref('')
const qrUser = ref('')

onShow(async () => {
  if (!requirePermission('dispatch.manage')) return
  await reload()
})

async function reload() {
  loading.value = true
  try {
    const r = await productionAdminApi.listDispatchAssignments({
      limit: 50,
      keyword: keyword.value.trim() || undefined,
    })
    items.value = r.items || []
  } catch {
    items.value = []
  } finally {
    loading.value = false
  }
}

async function openQr(row: DispatchAssignment) {
  try {
    const data = await productionAdminApi.getDispatchAssignmentQr(row.id)
    qrTaskCode.value = data.task_code || row.task_code
    qrUrl.value = data.report_url || data.text || ''
    qrUser.value = row.user_full_name || row.username || String(row.user_id)
    qrVisible.value = true
  } catch (e: unknown) {
    uni.showToast({ title: (e as Error).message || '获取失败', icon: 'none' })
  }
}

function copyText(text: string) {
  if (!text) {
    uni.showToast({ title: '无内容', icon: 'none' })
    return
  }
  uni.setClipboardData({
    data: text,
    success: () => uni.showToast({ title: '已复制', icon: 'success' }),
  })
}
</script>

<style scoped lang="scss">
.toolbar { display: flex; gap: 12rpx; margin-bottom: 20rpx; }
.search { flex: 1; background: #fff; border-radius: 999rpx; padding: 16rpx 28rpx; font-size: 26rpx; }
.refresh { background: #f1f5f9; color: #475569; border-radius: 999rpx; }
.mask { position: fixed; inset: 0; background: rgba(15,23,42,.45); z-index: 10000; display: flex; align-items: flex-end; }
.sheet { width: 100%; max-height: 75vh; background: #fff; border-radius: 24rpx 24rpx 0 0; }
.head { padding: 28rpx 32rpx; border-bottom: 1rpx solid #f1f5f9; }
.title { font-size: 32rpx; font-weight: 700; }
.body { max-height: 50vh; padding: 16rpx 32rpx; box-sizing: border-box; }
.kv { display: flex; gap: 16rpx; margin-bottom: 16rpx; font-size: 26rpx; }
.kv.col { flex-direction: column; gap: 8rpx; }
.k { color: #64748b; width: 120rpx; flex-shrink: 0; }
.v { color: #334155; flex: 1; word-break: break-all; }
.mono { font-family: monospace; }
.link { font-size: 24rpx; color: #4338ca; }
.hint { font-size: 24rpx; color: #94a3b8; margin-top: 12rpx; }
.foot { display: flex; gap: 12rpx; padding: 20rpx 32rpx calc(20rpx + env(safe-area-inset-bottom)); border-top: 1rpx solid #f1f5f9; }
.btn { flex: 1; border-radius: 12rpx; font-size: 26rpx; }
.ghost { background: #f1f5f9; color: #475569; }
.primary { background: linear-gradient(135deg, #6366f1, #4338ca); color: #fff; }
</style>
