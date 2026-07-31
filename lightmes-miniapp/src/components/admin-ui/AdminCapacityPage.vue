<template>
  <view class="adm-page">
    <view class="section">
      <text class="section-title">产能单位</text>
      <text class="hint">计件工厂请选「件/天」；自动派工与负荷按此单位计算。</text>
      <view class="unit-row">
        <view class="unit-btn" :class="{ active: unit === 'pieces' }" @tap="switchUnit('pieces')">计件（件/天）</view>
        <view class="unit-btn" :class="{ active: unit === 'minutes' }" @tap="switchUnit('minutes')">工时（分钟/天）</view>
      </view>
    </view>

    <view class="section">
      <text class="section-title">默认日产能</text>
      <text class="hint">仅「员工」角色（与自动派工一致）；未单独配置的使用默认产能（{{ unitLabel }}）</text>
      <view class="field inline">
        <input v-model.number="defaultCapacity" type="number" class="input" />
        <text class="unit-suffix">{{ unitLabel }}</text>
      </view>
      <button class="btn primary" :loading="savingDefault" @tap="saveDefault">保存默认产能</button>
    </view>

    <view class="section">
      <view class="section-head">
        <text class="section-title">人员产能</text>
        <text class="link" @tap="loadUsers">刷新</text>
      </view>
      <view v-if="userLoading" class="hint">加载中...</view>
      <view v-for="row in userRows" :key="row.user_id" class="cap-row">
        <text class="cap-name">{{ row.name }}</text>
        <input v-model.number="row.capacity_minutes" type="number" class="cap-input" :placeholder="String(defaultCapacity)" />
        <text class="cap-unit">{{ unitLabel }}</text>
      </view>
      <button class="btn ghost" :loading="savingUsers" @tap="saveUsers">保存人员覆盖</button>
    </view>

    <view class="section">
      <view class="section-head">
        <text class="section-title">车间产能</text>
        <text class="link" @tap="loadWorkshops">刷新</text>
      </view>
      <view v-if="wsLoading" class="hint">加载中...</view>
      <view v-for="row in wsRows" :key="row.workshop" class="cap-row">
        <text class="cap-name">{{ row.workshop }}</text>
        <input v-model.number="row.capacity_minutes" type="number" class="cap-input" :placeholder="String(defaultCapacity)" />
        <text class="cap-unit">{{ unitLabel }}</text>
      </view>
      <button class="btn ghost" :loading="savingWs" @tap="saveWorkshops">保存车间覆盖</button>
    </view>
  </view>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { onShow } from '@dcloudio/uni-app'
import { plansAdminApi } from '@/api/admin/plans'
import { masterAdminApi } from '@/api/admin/master'
import { usePermission } from '@/composables/usePermission'

const { requirePermission } = usePermission()

const unit = ref<'pieces' | 'minutes'>('pieces')
const defaultCapacity = ref(300)
const savingDefault = ref(false)
const savingUsers = ref(false)
const savingWs = ref(false)
const userLoading = ref(false)
const wsLoading = ref(false)

const userRows = ref<{ user_id: number; name: string; capacity_minutes: number }[]>([])
const wsRows = ref<{ workshop: string; capacity_minutes: number }[]>([])

const unitLabel = computed(() => (unit.value === 'pieces' ? '件/天' : '分钟/天'))

onShow(async () => {
  if (!requirePermission('plan.manage')) return
  await loadMeta()
  await Promise.all([loadUsers(), loadWorkshops()])
})

async function loadMeta() {
  const meta = await plansAdminApi.getCapacity()
  defaultCapacity.value = meta.capacity || 300
  unit.value = meta.unit || 'pieces'
}

async function switchUnit(u: 'pieces' | 'minutes') {
  if (unit.value === u) return
  try {
    const meta = await plansAdminApi.setCapacityUnit(u)
    unit.value = meta.unit
    defaultCapacity.value = meta.capacity
    uni.showToast({ title: `已切换为${meta.unit_label || unitLabel.value}`, icon: 'success' })
    await Promise.all([loadUsers(), loadWorkshops()])
  } catch (e: unknown) {
    uni.showToast({ title: (e as Error).message || '切换失败', icon: 'none' })
  }
}

async function saveDefault() {
  const cap = Number(defaultCapacity.value)
  if (!cap || cap < 1) {
    uni.showToast({ title: '请输入有效产能', icon: 'none' })
    return
  }
  savingDefault.value = true
  try {
    const meta = await plansAdminApi.setCapacity(cap)
    defaultCapacity.value = meta.capacity
    unit.value = meta.unit
    uni.showToast({ title: '已保存', icon: 'success' })
  } catch (e: unknown) {
    uni.showToast({ title: (e as Error).message || '保存失败', icon: 'none' })
  } finally {
    savingDefault.value = false
  }
}

async function loadUsers() {
  userLoading.value = true
  try {
    const capRes = await plansAdminApi.getUserCapacityRows()
    defaultCapacity.value = capRes.default_capacity || defaultCapacity.value
    if (capRes.unit === 'pieces' || capRes.unit === 'minutes') unit.value = capRes.unit
    userRows.value = (capRes.items || []).map((x) => ({
      user_id: x.user_id,
      name: x.name,
      capacity_minutes: x.capacity_minutes ?? 0,
    }))
  } finally {
    userLoading.value = false
  }
}

async function saveUsers() {
  savingUsers.value = true
  try {
    const def = defaultCapacity.value
    const items = userRows.value
      .filter((x) => x.capacity_minutes > 0 && x.capacity_minutes !== def)
      .map((x) => ({ user_id: x.user_id, capacity_minutes: x.capacity_minutes }))
    await plansAdminApi.setUserCapacities(items)
    uni.showToast({ title: '人员产能已保存', icon: 'success' })
  } catch (e: unknown) {
    uni.showToast({ title: (e as Error).message || '保存失败', icon: 'none' })
  } finally {
    savingUsers.value = false
  }
}

async function loadWorkshops() {
  wsLoading.value = true
  try {
    const [capRes, procRes] = await Promise.all([
      plansAdminApi.getWorkshopCapacities(),
      masterAdminApi.listProcesses(),
    ])
    defaultCapacity.value = capRes.default_capacity || defaultCapacity.value
    if (capRes.unit === 'pieces' || capRes.unit === 'minutes') unit.value = capRes.unit
    const workshops = new Set<string>()
    for (const p of procRes.items || []) {
      const w = String((p as { workshop?: string }).workshop || '').trim()
      if (w) workshops.add(w)
    }
    workshops.add('未分车间')
    const capMap = new Map((capRes.items || []).map((x) => [x.workshop, x.capacity_minutes]))
    wsRows.value = Array.from(workshops)
      .sort((a, b) => a.localeCompare(b))
      .map((w) => ({ workshop: w, capacity_minutes: capMap.get(w) ?? 0 }))
  } finally {
    wsLoading.value = false
  }
}

async function saveWorkshops() {
  savingWs.value = true
  try {
    const def = defaultCapacity.value
    const items = wsRows.value
      .filter((x) => x.capacity_minutes > 0 && x.capacity_minutes !== def)
      .map((x) => ({ workshop: x.workshop, capacity_minutes: x.capacity_minutes }))
    await plansAdminApi.setWorkshopCapacities(items)
    uni.showToast({ title: '车间产能已保存', icon: 'success' })
  } catch (e: unknown) {
    uni.showToast({ title: (e as Error).message || '保存失败', icon: 'none' })
  } finally {
    savingWs.value = false
  }
}
</script>

<style scoped lang="scss">
.section { background: #fff; border-radius: 16rpx; padding: 28rpx; margin-bottom: 24rpx; }
.section-head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 16rpx; }
.section-title { display: block; font-size: 32rpx; font-weight: 700; margin-bottom: 12rpx; }
.hint { display: block; font-size: 24rpx; color: #64748b; margin-bottom: 16rpx; line-height: 1.5; }
.link { font-size: 24rpx; color: #4338ca; }
.unit-row { display: flex; gap: 16rpx; margin-bottom: 8rpx; }
.unit-btn {
  flex: 1; text-align: center; padding: 20rpx; border-radius: 12rpx; font-size: 26rpx;
  background: #f1f5f9; color: #475569;
  &.active { background: #eef2ff; color: #4338ca; font-weight: 600; }
}
.field.inline { display: flex; align-items: center; gap: 12rpx; margin-bottom: 20rpx; }
.input { flex: 1; background: #f8fafc; border-radius: 12rpx; padding: 20rpx; font-size: 28rpx; }
.unit-suffix { font-size: 26rpx; color: #64748b; white-space: nowrap; }
.cap-row { display: flex; align-items: center; gap: 12rpx; padding: 16rpx 0; border-bottom: 1rpx solid #f1f5f9; }
.cap-name { flex: 1; font-size: 26rpx; color: #334155; min-width: 0; overflow: hidden; text-overflow: ellipsis; }
.cap-input { width: 160rpx; background: #f8fafc; border-radius: 8rpx; padding: 12rpx; font-size: 26rpx; text-align: right; }
.cap-unit { font-size: 22rpx; color: #94a3b8; width: 88rpx; }
.btn { border-radius: 12rpx; font-size: 28rpx; margin-top: 16rpx; }
.primary { background: linear-gradient(135deg, #6366f1, #4338ca); color: #fff; }
.ghost { background: #f1f5f9; color: #475569; }
</style>
