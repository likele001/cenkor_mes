<template>
  <view class="adm-page">
    <view class="toolbar">
      <button class="add-btn" size="mini" @tap="openCreate">+ 新建</button>
    </view>
    <MListLayout :items="items" :loading="loading" empty-text="暂无工艺路线" :tap-to-select="false">
      <template #item="{ item }">
        <view class="adm-list-head">
          <text class="adm-list-title">{{ item.name }}</text>
          <text v-if="item.is_default" class="adm-list-badge tone-success">默认</text>
        </view>
        <AdminKvGrid :rows="[
          { label: '产品', value: productName(item.product_id) },
          { label: '工序', value: stepsPreview(item.steps) },
        ]" />
      </template>
      <template #actions="{ item }">
        <view class="adm-card-btns">
          <button class="adm-card-btn edit" @tap="openEdit(item)">编辑</button>
        </view>
      </template>
    </MListLayout>

    <view v-if="formVisible" class="mask" @tap="formVisible = false">
      <view class="sheet" @tap.stop>
        <view class="head"><text class="title">{{ formMode === 'create' ? '新建工艺路线' : '编辑工艺路线' }}</text></view>
        <scroll-view scroll-y class="body">
          <view class="field">
            <text class="label">产品*</text>
            <picker :range="productLabels" @change="onProductPick">
              <view class="input picker">{{ productLabels[productIndex] || '请选择' }}</view>
            </picker>
          </view>
          <view class="field"><text class="label">名称*</text><input v-model="form.name" class="input" /></view>
          <view class="field row-switch">
            <text class="label">默认路线</text>
            <switch :checked="form.is_default" @change="(e) => (form.is_default = e.detail.value)" />
          </view>
          <view class="lines-head">
            <text class="label">工序步骤*</text>
            <text class="link" @tap="addStep">+ 添加</text>
          </view>
          <view v-for="(step, idx) in steps" :key="idx" class="line-card">
            <input v-model="step.seq" class="input seq" type="number" placeholder="序" />
            <picker :range="processLabels" @change="(e) => onProcessPick(idx, e)">
              <view class="input picker flex1">{{ processLabels[step.processIndex ?? 0] || '选工序' }}</view>
            </picker>
            <text class="del" @tap="removeStep(idx)">删</text>
          </view>
        </scroll-view>
        <view class="foot">
          <button v-if="formMode === 'edit'" class="btn ghost danger" @tap="disableRoute">停用</button>
          <button class="btn primary" :loading="saving" @tap="submit">保存</button>
        </view>
      </view>
    </view>
  </view>
</template>

<script setup lang="ts">
import { computed, reactive, ref } from 'vue'
import { onShow } from '@dcloudio/uni-app'
import AdminKvGrid from '@/components/admin-ui/AdminKvGrid.vue'
import MListLayout from '@/components/admin-ui/MListLayout.vue'
import { masterAdminApi, type ProcessRouteOut, type ProcessRouteStep } from '@/api/admin/master'
import { usePermission } from '@/composables/usePermission'

type StepRow = { seq: string; processIndex?: number; process_id?: number }

const { requirePermission } = usePermission()
const items = ref<ProcessRouteOut[]>([])
const products = ref<{ id: number; name: string; code?: string; display_name?: string }[]>([])
const processes = ref<{ id: number; name: string; code?: string }[]>([])
const loading = ref(false)
const formVisible = ref(false)
const formMode = ref<'create' | 'edit'>('create')
const saving = ref(false)
const editingId = ref<number | null>(null)
const productIndex = ref(0)
const form = reactive({ name: '', is_default: false })
const steps = ref<StepRow[]>([{ seq: '1', processIndex: 0 }])

const productLabels = computed(() => products.value.map((p) => p.display_name || p.name || p.code || String(p.id)))
const processLabels = computed(() => processes.value.map((p) => `${p.name}(${p.code || p.id})`))

onShow(async () => {
  if (!requirePermission('product.manage')) return
  await loadOptions()
  await reload()
})

function productName(id: number) {
  const p = products.value.find((x) => x.id === id)
  return p ? productLabels.value[products.value.indexOf(p)] : `#${id}`
}
function stepsPreview(st?: ProcessRouteStep[]) {
  if (!st?.length) return '无步骤'
  const m = new Map(processes.value.map((p) => [p.id, p.name]))
  return [...st].sort((a, b) => a.seq - b.seq).map((s) => `${s.seq}.${m.get(s.process_id) || s.process_id}`).join('→')
}

async function loadOptions() {
  try {
    const [p, proc] = await Promise.all([masterAdminApi.listProducts(), masterAdminApi.listProcesses()])
    products.value = p.items || []
    processes.value = proc.items || []
  } catch {
    products.value = []
    processes.value = []
  }
}

async function reload() {
  loading.value = true
  try {
    const r = await masterAdminApi.listProcessRoutes({ limit: 50 })
    items.value = r.items || []
  } catch {
    items.value = []
  } finally {
    loading.value = false
  }
}

function onProductPick(e: { detail: { value: number } }) { productIndex.value = Number(e.detail.value) }
function onProcessPick(idx: number, e: { detail: { value: number } }) {
  steps.value[idx].processIndex = Number(e.detail.value)
  steps.value[idx].process_id = processes.value[steps.value[idx].processIndex!]?.id
}
function addStep() { steps.value.push({ seq: String(steps.value.length + 1), processIndex: 0 }) }
function removeStep(idx: number) { if (steps.value.length > 1) steps.value.splice(idx, 1) }

function openCreate() {
  formMode.value = 'create'
  editingId.value = null
  productIndex.value = 0
  form.name = ''
  form.is_default = false
  steps.value = [{ seq: '1', processIndex: 0 }]
  formVisible.value = true
}

async function openEdit(row: ProcessRouteOut) {
  formMode.value = 'edit'
  editingId.value = row.id
  try {
    const d = await masterAdminApi.getProcessRoute(row.id)
    productIndex.value = Math.max(0, products.value.findIndex((p) => p.id === d.product_id))
    form.name = d.name
    form.is_default = !!d.is_default
    steps.value = (d.steps || []).length
      ? d.steps!.map((s) => ({
          seq: String(s.seq),
          process_id: s.process_id,
          processIndex: Math.max(0, processes.value.findIndex((p) => p.id === s.process_id)),
        }))
      : [{ seq: '1', processIndex: 0 }]
    formVisible.value = true
  } catch {
    uni.showToast({ title: '加载失败', icon: 'none' })
  }
}

function buildPayload() {
  const product = products.value[productIndex.value]
  if (!product) throw new Error('请选择产品')
  if (!form.name.trim()) throw new Error('请输入名称')
  const mapped = steps.value.map((s) => {
    const proc = processes.value[s.processIndex ?? 0]
    const seq = Number(s.seq)
    if (!seq || seq <= 0) throw new Error('步骤序号须>0')
    if (!proc && !s.process_id) throw new Error('请选择工序')
    return { seq, process_id: s.process_id || proc!.id }
  })
  if (!mapped.length) throw new Error('请添加步骤')
  const seqs = mapped.map((x) => x.seq)
  if (new Set(seqs).size !== seqs.length) throw new Error('步骤序号不能重复')
  return {
    product_id: product.id,
    name: form.name.trim(),
    is_default: form.is_default,
    is_active: true,
    steps: mapped,
  }
}

async function submit() {
  saving.value = true
  try {
    const payload = buildPayload()
    if (formMode.value === 'create') {
      await masterAdminApi.createProcessRoute(payload)
      uni.showToast({ title: '创建成功', icon: 'success' })
    } else if (editingId.value) {
      await masterAdminApi.updateProcessRoute(editingId.value, payload)
      uni.showToast({ title: '保存成功', icon: 'success' })
    }
    formVisible.value = false
    await reload()
  } catch (e: unknown) {
    uni.showToast({ title: (e as Error).message || '保存失败', icon: 'none' })
  } finally {
    saving.value = false
  }
}

function disableRoute() {
  if (!editingId.value) return
  uni.showModal({
    title: '停用路线',
    content: '确认停用？',
    success: async (res) => {
      if (!res.confirm || !editingId.value) return
      await masterAdminApi.disableProcessRoute(editingId.value)
      uni.showToast({ title: '已停用', icon: 'success' })
      formVisible.value = false
      await reload()
    },
  })
}
</script>

<style scoped lang="scss">
.toolbar { margin-bottom: 20rpx; }
.add-btn { background: linear-gradient(135deg, #6366f1, #4338ca); color: #fff; border-radius: 999rpx; }
.mask { position: fixed; inset: 0; background: rgba(15,23,42,.45); z-index: 10000; display: flex; align-items: flex-end; }
.sheet { width: 100%; max-height: 85vh; background: #fff; border-radius: 24rpx 24rpx 0 0; }
.head { padding: 28rpx 32rpx; border-bottom: 1rpx solid #f1f5f9; }
.title { font-size: 32rpx; font-weight: 700; }
.body { max-height: 58vh; padding: 16rpx 32rpx; box-sizing: border-box; }
.field { margin-bottom: 20rpx; }
.row-switch { display: flex; align-items: center; justify-content: space-between; }
.label { display: block; font-size: 26rpx; color: #475569; margin-bottom: 8rpx; }
.input { background: #f8fafc; border-radius: 12rpx; padding: 20rpx; font-size: 28rpx; }
.picker { color: #334155; }
.flex1 { flex: 1; }
.seq { width: 100rpx; flex-shrink: 0; }
.lines-head { display: flex; justify-content: space-between; margin: 12rpx 0; }
.link { color: #4338ca; font-size: 26rpx; }
.line-card { display: flex; gap: 8rpx; align-items: center; margin-bottom: 12rpx; }
.del { color: #ef4444; font-size: 24rpx; }
.foot { display: flex; gap: 12rpx; padding: 20rpx 32rpx calc(20rpx + env(safe-area-inset-bottom)); border-top: 1rpx solid #f1f5f9; }
.btn { flex: 1; border-radius: 12rpx; font-size: 26rpx; }
.ghost { background: #f1f5f9; color: #475569; }
.primary { background: linear-gradient(135deg, #6366f1, #4338ca); color: #fff; }
.danger { color: #ef4444; }
</style>
