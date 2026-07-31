<template>
  <view class="adm-page">
    <view class="toolbar">
      <input v-model="keyword" class="search" placeholder="任务码/状态" @confirm="reload" />
      <button class="refresh" size="mini" @tap="reload">刷新</button>
    </view>

    <MListLayout :items="items" :loading="loading" empty-text="暂无任务" :tap-to-select="false">
      <template #item="{ item }">
        <view class="adm-list-head">
          <text class="adm-list-title">{{ orderLabel(item) || taskTitle(item) }}</text>
          <text class="adm-list-badge tone-active">{{ statusLabel(item.status) }}</text>
        </view>
        <text class="adm-list-subtitle">{{ taskTitle(item) }}</text>
        <AdminKvGrid :rows="taskKvRows(item)" />
      </template>
      <template #actions="{ item }">
        <view class="adm-card-btns">
          <button class="adm-card-btn edit" @tap="openAssign(item)">派工</button>
          <button class="adm-card-btn primary" @tap="openAssign(item)">编辑</button>
        </view>
      </template>
    </MListLayout>

    <view v-if="assignVisible" class="mask" @tap="assignVisible = false">
      <view class="sheet" @tap.stop>
        <view class="head">
          <text class="title">任务派工</text>
          <text class="sub">计划 {{ plannedQty }} · 已派 {{ assignedTotal }}</text>
        </view>
        <scroll-view scroll-y class="body">
          <view class="field">
            <text class="label">设备(可选)</text>
            <picker :range="equipmentLabels" @change="onEquipmentPick">
              <view class="input picker">{{ equipmentLabels[equipmentIndex] || '不指定设备' }}</view>
            </picker>
          </view>
          <view class="lines-head">
            <text class="label">派工明细</text>
            <text class="link" @tap="addRow">+ 添加员工</text>
          </view>
          <view v-for="(row, idx) in rows" :key="idx" class="line-card">
            <picker :range="userLabels" @change="(e) => onUserPick(idx, e)">
              <view class="input picker flex1">{{ userLabels[row.userIndex ?? 0] || '选员工' }}</view>
            </picker>
            <input v-model="row.assigned_qty" class="input qty" type="number" placeholder="数量" />
            <text class="del" @tap="removeRow(idx)">删</text>
          </view>
        </scroll-view>
        <view class="foot">
          <button class="btn ghost danger" @tap="cancelAssign">取消派工</button>
          <button class="btn primary" :loading="saving" @tap="saveAssign">保存</button>
        </view>
      </view>
    </view>
  </view>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { onShow } from '@dcloudio/uni-app'
import AdminKvGrid from '@/components/admin-ui/AdminKvGrid.vue'
import MListLayout from '@/components/admin-ui/MListLayout.vue'
import { productionAdminApi, type TaskOut } from '@/api/admin/production'
import { usePermission } from '@/composables/usePermission'
import { formatDateTime } from '@/utils/taskDisplay'

const props = defineProps<{ initialTaskId?: number | null }>()

type AssignRow = { userIndex?: number; user_id?: number; assigned_qty: string; reported_qty?: number }

const { requirePermission } = usePermission()
const items = ref<TaskOut[]>([])
const users = ref<{ id: number; username: string; full_name?: string }[]>([])
const equipments = ref<{ id: number; code: string; name: string }[]>([])
const loading = ref(false)
const keyword = ref('')
const assignVisible = ref(false)
const saving = ref(false)
const taskId = ref<number | null>(null)
const plannedQty = ref(0)
const equipmentIndex = ref(0)
const rows = ref<AssignRow[]>([{ assigned_qty: '1', userIndex: 0 }])
const pendingOpenTaskId = ref<number | null>(null)

const userLabels = computed(() => users.value.map((u) => (u.full_name ? `${u.full_name}(${u.username})` : u.username)))
const equipmentLabels = computed(() => ['不指定设备', ...equipments.value.map((e) => `${e.name}(${e.code})`)])
const assignedTotal = computed(() =>
  rows.value.reduce((s, r) => s + (r.user_id ? Number(r.assigned_qty) || 0 : 0), 0),
)

onShow(async () => {
  if (!requirePermission('dispatch.manage')) return
  if (props.initialTaskId) pendingOpenTaskId.value = props.initialTaskId
  await loadUsers()
  await loadEquipments()
  await reload()
  await tryOpenPendingTask()
})

function assignLabel(item: TaskOut) {
  const total = Number(item.assigned_total_qty ?? 0)
  const count = item.assignments?.length ?? (total > 0 ? 1 : 0)
  if (!total && !count) return '未派工'
  return `${count}人 ${total}/${item.planned_qty}`
}

function mergeTaskItem(task: TaskOut, emitEvent = false) {
  const idx = items.value.findIndex((t) => t.id === task.id)
  if (idx >= 0) {
    items.value.splice(idx, 1, { ...items.value[idx], ...task })
  } else {
    items.value.unshift(task)
  }
  items.value = [...items.value]
  if (emitEvent) uni.$emit('admin:task-assign-updated', task)
}

function processLabel(item: TaskOut) {
  const p = item.process
  return p?.display_name || p?.name || p?.code || '工序'
}
function taskTitle(item: TaskOut) {
  return item.sku?.display_label || item.sku?.display_name || item.sku?.name || item.task_code || `#${item.id}`
}
function orderLabel(item: TaskOut) {
  return item.order?.code || (item.work_order?.order_id ? `#${item.work_order.order_id}` : '—')
}
function statusLabel(s: string) {
  const map: Record<string, string> = { pending: '待完成', working: '进行中', done: '已完成' }
  return map[s] || s
}

function taskKvRows(item: TaskOut) {
  return [
    { label: '产品', value: item.sku?.display_label || item.sku?.name || '—' },
    { label: '工序', value: processLabel(item) },
    { label: '计划数量', value: String(item.planned_qty ?? 0) },
    { label: '派工情况', value: assignLabel(item) },
    { label: '创建时间', value: formatDateTime(item.created_at) },
  ]
}

async function loadUsers() {
  try {
    const r = await productionAdminApi.listDispatchUsers({ limit: 100 })
    users.value = r.items || []
  } catch {
    users.value = []
  }
}

async function loadEquipments() {
  try {
    const r = await productionAdminApi.listEquipment()
    equipments.value = r.items || []
  } catch {
    equipments.value = []
  }
}

async function reload(preserveTask?: TaskOut) {
  loading.value = true
  try {
    const r = await productionAdminApi.listTasks({
      limit: 50,
      keyword: keyword.value.trim() || undefined,
      _ts: Date.now(),
    })
    items.value = r.items || []
    if (preserveTask) mergeTaskItem(preserveTask)
  } catch {
    if (!preserveTask) items.value = []
  } finally {
    loading.value = false
  }
}

async function tryOpenPendingTask() {
  const id = pendingOpenTaskId.value
  if (!id) return
  pendingOpenTaskId.value = null
  const row = items.value.find((t) => t.id === id)
  if (row) await openAssign(row)
}

function syncRowUserIds() {
  for (const row of rows.value) {
    if (row.userIndex != null && row.userIndex >= 0 && users.value[row.userIndex]) {
      row.user_id = users.value[row.userIndex].id
    }
  }
}

async function openAssign(row: TaskOut) {
  taskId.value = row.id
  plannedQty.value = row.planned_qty
  equipmentIndex.value = row.equipment_id
    ? Math.max(0, equipments.value.findIndex((e) => e.id === row.equipment_id) + 1)
    : 0
  try {
    const res = await productionAdminApi.getTaskAssignments(row.id)
    plannedQty.value = res.planned_qty
    const its = res.items || []
    rows.value = its.length
      ? its.map((it) => ({
          user_id: it.user_id,
          userIndex: Math.max(0, users.value.findIndex((u) => u.id === it.user_id)),
          assigned_qty: String(it.assigned_qty),
          reported_qty: it.reported_qty ?? 0,
        }))
      : [{ assigned_qty: '1', userIndex: 0 }]
    for (const it of its) {
      if (it.user && !users.value.find((u) => u.id === it.user!.id)) {
        users.value.push(it.user)
      }
    }
  } catch {
    rows.value = [{ assigned_qty: String(row.planned_qty || 1), userIndex: 0 }]
  }
  syncRowUserIds()
  assignVisible.value = true
}

function onEquipmentPick(e: { detail: { value: number } }) {
  equipmentIndex.value = Number(e.detail.value)
}
function onUserPick(idx: number, e: { detail: { value: number } }) {
  rows.value[idx].userIndex = Number(e.detail.value)
  rows.value[idx].user_id = users.value[rows.value[idx].userIndex!]?.id
}
function addRow() {
  rows.value.push({ assigned_qty: '1', userIndex: 0 })
  syncRowUserIds()
}
function removeRow(idx: number) {
  if (rows.value.length <= 1) return
  rows.value.splice(idx, 1)
}

function buildPayload() {
  syncRowUserIds()
  const mapped = rows.value
    .filter((r) => r.user_id)
    .map((r) => ({ user_id: Number(r.user_id), assigned_qty: Number(r.assigned_qty) }))
  const ids = mapped.map((x) => x.user_id)
  if (new Set(ids).size !== ids.length) throw new Error('同一员工不能重复派工')
  if (assignedTotal.value > plannedQty.value) throw new Error(`派工合计不能超过计划数 ${plannedQty.value}`)
  for (const r of rows.value) {
    if (r.user_id && (r.reported_qty ?? 0) > Number(r.assigned_qty)) {
      throw new Error('派工数不能小于已报工数')
    }
  }
  const eqIdx = equipmentIndex.value
  const equipment_id = eqIdx > 0 ? equipments.value[eqIdx - 1]?.id ?? null : null
  return { items: mapped, equipment_id }
}

async function saveAssign() {
  if (!taskId.value) return
  saving.value = true
  try {
    const updated = await productionAdminApi.setTaskAssignments(taskId.value, buildPayload())
    assignVisible.value = false
    mergeTaskItem(updated, true)
    await reload(updated)
    uni.showToast({ title: '派工已保存', icon: 'success' })
  } catch (e: unknown) {
    uni.showToast({ title: (e as Error).message || '保存失败', icon: 'none' })
  } finally {
    saving.value = false
  }
}

function cancelAssign() {
  if (!taskId.value) return
  uni.showModal({
    title: '取消派工',
    content: '确认取消该任务全部派工？',
    success: async (res) => {
      if (!res.confirm || !taskId.value) return
      saving.value = true
      try {
        const updated = await productionAdminApi.setTaskAssignments(taskId.value, { items: [], equipment_id: null })
        assignVisible.value = false
        mergeTaskItem(updated, true)
        await reload(updated)
        uni.showToast({ title: '已取消派工', icon: 'success' })
      } catch (e: unknown) {
        uni.showToast({ title: (e as Error).message || '操作失败', icon: 'none' })
      } finally {
        saving.value = false
      }
    },
  })
}
</script>

<style scoped lang="scss">
.toolbar { display: flex; gap: 12rpx; margin-bottom: 20rpx; }
.search { flex: 1; background: #fff; border-radius: 999rpx; padding: 16rpx 28rpx; font-size: 26rpx; }
.refresh { background: #f1f5f9; color: #475569; border-radius: 999rpx; }
.mask { position: fixed; inset: 0; background: rgba(15,23,42,.45); z-index: 10000; display: flex; align-items: flex-end; }
.sheet { width: 100%; max-height: 85vh; background: #fff; border-radius: 24rpx 24rpx 0 0; }
.head { padding: 28rpx 32rpx; border-bottom: 1rpx solid #f1f5f9; }
.title { display: block; font-size: 32rpx; font-weight: 700; }
.sub { display: block; font-size: 24rpx; color: #64748b; margin-top: 6rpx; }
.body { max-height: 58vh; padding: 16rpx 32rpx; box-sizing: border-box; }
.field { margin-bottom: 20rpx; }
.label { display: block; font-size: 26rpx; color: #475569; margin-bottom: 8rpx; }
.input { background: #f8fafc; border-radius: 12rpx; padding: 20rpx; font-size: 28rpx; }
.picker { color: #334155; }
.flex1 { flex: 1; }
.lines-head { display: flex; justify-content: space-between; align-items: center; margin: 12rpx 0; }
.link { color: #4338ca; font-size: 26rpx; }
.line-card { display: flex; gap: 8rpx; align-items: center; margin-bottom: 12rpx; }
.qty { width: 140rpx; flex-shrink: 0; }
.del { color: #ef4444; font-size: 24rpx; padding: 8rpx; }
.foot { display: flex; gap: 12rpx; padding: 20rpx 32rpx calc(20rpx + env(safe-area-inset-bottom)); border-top: 1rpx solid #f1f5f9; }
.btn { flex: 1; border-radius: 12rpx; font-size: 26rpx; }
.ghost { background: #f1f5f9; color: #475569; }
.primary { background: linear-gradient(135deg, #6366f1, #4338ca); color: #fff; }
.danger { color: #ef4444; }
</style>
