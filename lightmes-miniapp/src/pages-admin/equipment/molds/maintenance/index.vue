<template>
  <view class="adm-page">
    <view class="adm-section-head" v-if="moldName">
      <text class="adm-section-title">{{ moldName }} 的维保记录</text>
    </view>

    <view class="adm-card" v-for="log in logs" :key="log.id">
      <view class="field-label">{{ MAINT_TYPES[log.maintenance_type] || log.maintenance_type }}</view>
      <AdminKvGrid :rows="[
        { label: '描述', value: log.description || '—' },
        { label: '模次', value: log.shots_at_maintenance != null ? String(log.shots_at_maintenance) : '—' },
        { label: '时间', value: log.created_at?.slice(0, 16) || '—' },
      ]" />
    </view>
    <view v-if="!logs.length && !loading" class="adm-empty-tip">暂无维保记录</view>

    <view class="sheet-add">
      <view class="adm-section-head">
        <text class="adm-section-title">新增维保</text>
      </view>
      <view class="field">
        <text class="label">类型</text>
        <picker :range="Object.values(MAINT_TYPES)" @change="e => newLogType = Object.keys(MAINT_TYPES)[e.detail.value]">
          <view class="input picker">{{ MAINT_TYPES[newLogType] }}</view>
        </picker>
      </view>
      <view class="field">
        <text class="label">描述</text>
        <textarea v-model="newLogDesc" class="textarea" placeholder="可选" />
      </view>
      <button class="btn primary" :loading="saving" @tap="submitLog">保存</button>
    </view>
  </view>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { onLoad } from '@dcloudio/uni-app'
import { moldApi, type MoldMaintenanceLog } from '@/api/admin/mold'
import AdminKvGrid from '@/components/admin-ui/AdminKvGrid.vue'

const MAINT_TYPES: Record<string, string> = {
  daily: '日常保养', level1: '一级保养', level2: '二级保养',
  overhaul: '大修', repair: '维修',
}

const moldId = ref(0)
const moldName = ref('')
const logs = ref<MoldMaintenanceLog[]>([])
const loading = ref(false)
const newLogType = ref('daily')
const newLogDesc = ref('')
const saving = ref(false)

onLoad((q) => {
  moldId.value = Number(q?.moldId || 0)
  moldName.value = q?.name ? decodeURIComponent(q.name as string) : ''
  loadLogs()
})

async function loadLogs() {
  if (!moldId.value) return
  loading.value = true
  try {
    const r = await moldApi.listMaintenanceLogs(moldId.value)
    logs.value = r.items
  } catch { logs.value = [] }
  finally { loading.value = false }
}

async function submitLog() {
  if (!moldId.value) return
  saving.value = true
  try {
    await moldApi.createMaintenanceLog(moldId.value, {
      maintenance_type: newLogType.value,
      description: newLogDesc.value.trim() || undefined,
    })
    uni.showToast({ title: '保存成功', icon: 'success' })
    newLogDesc.value = ''
    newLogType.value = 'daily'
    await loadLogs()
  } catch { /* handled */ }
  finally { saving.value = false }
}
</script>

<style scoped>
.sheet-add { background: #fff; border-radius: 20rpx; padding: 28rpx; margin-top: 20rpx; }
.field-label { font-size: 28rpx; font-weight: 600; color: #1e293b; margin-bottom: 12rpx; }
</style>
