<template>
  <view class="adm-page">
    <view class="toolbar">
      <input v-model="keyword" class="search" placeholder="搜索BOM" @confirm="reload" />
      <button class="add-btn" size="mini" @tap="openCreate">+ 新建</button>
    </view>
    <MListLayout :items="items" :loading="loading" empty-text="暂无BOM" :tap-to-select="false">
      <template #item="{ item }">
        <view class="adm-list-head">
          <text class="adm-list-title">{{ item.name || item.sku_name || item.product_name || `BOM#${item.id}` }}</text>
          <text class="adm-list-badge tone-active">v{{ item.version ?? 1 }}</text>
        </view>
        <AdminKvGrid :rows="[
          { label: '类型', value: item.scope_label || item.scope || '—' },
          { label: '版本', value: String(item.version ?? 1) },
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
        <view class="head"><text class="title">{{ formMode === 'create' ? '新建BOM' : '编辑BOM' }}</text></view>
        <scroll-view scroll-y class="body">
          <view v-if="formMode === 'create'" class="field">
            <text class="label">类型*</text>
            <picker :range="scopeLabels" @change="onScopePick">
              <view class="input picker">{{ scopeLabels[scopeIndex] }}</view>
            </picker>
          </view>
          <view v-if="form.scope === 'sku' && formMode === 'create'" class="field">
            <text class="label">型号*</text>
            <picker :range="skuLabels" @change="onSkuPick">
              <view class="input picker">{{ skuLabels[skuIndex] || '请选择' }}</view>
            </picker>
          </view>
          <view v-if="form.scope === 'product' && formMode === 'create'" class="field">
            <text class="label">产品*</text>
            <picker :range="productLabels" @change="onProductPick">
              <view class="input picker">{{ productLabels[productIndex] || '请选择' }}</view>
            </picker>
          </view>
          <view v-if="form.scope === 'global'" class="field">
            <text class="label">模板名称</text>
            <input v-model="form.name" class="input" placeholder="如：通用BOM" />
          </view>
          <view class="field"><text class="label">版本</text><input v-model="form.version" class="input" type="number" /></view>
          <view class="field"><text class="label">备注</text><textarea v-model="form.remark" class="input area" /></view>
          <view class="lines-head">
            <text class="label">明细*</text>
            <text class="link" @tap="addLine">+ 添加行</text>
          </view>
          <view v-for="(line, idx) in lines" :key="idx" class="line-card">
            <picker :range="materialLabels" @change="(e) => onMaterialPick(idx, e)">
              <view class="input picker flex1">{{ materialLabels[line.materialIndex ?? 0] || '选物料' }}</view>
            </picker>
            <input v-model="line.qty_per" class="input qty" type="digit" placeholder="单耗" />
            <text class="del" @tap="removeLine(idx)">删</text>
          </view>
        </scroll-view>
        <view class="foot">
          <button v-if="formMode === 'edit'" class="btn ghost danger" @tap="disableBom">停用</button>
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
import { masterAdminApi, type BomOut } from '@/api/admin/master'
import { usePermission } from '@/composables/usePermission'

type Line = { materialIndex?: number; material_id?: number; qty_per: string; remark?: string; id?: number }
const scopes = [
  { value: 'global', label: '全厂默认' },
  { value: 'product', label: '产品默认' },
  { value: 'sku', label: '型号专属' },
]

const { requirePermission } = usePermission()
const items = ref<BomOut[]>([])
const materials = ref<{ id: number; name: string; code?: string }[]>([])
const skus = ref<{ id: number; display_label?: string; name?: string; code?: string }[]>([])
const products = ref<{ id: number; name: string; code?: string; display_name?: string }[]>([])
const loading = ref(false)
const keyword = ref('')
const formVisible = ref(false)
const formMode = ref<'create' | 'edit'>('create')
const saving = ref(false)
const editingId = ref<number | null>(null)
const scopeIndex = ref(2)
const skuIndex = ref(0)
const productIndex = ref(0)
const form = reactive({ scope: 'sku', name: '', version: '1', remark: '' })
const lines = ref<Line[]>([{ qty_per: '1', materialIndex: 0 }])

const scopeLabels = scopes.map((s) => s.label)
const materialLabels = computed(() => materials.value.map((m) => `${m.name}(${m.code || m.id})`))
const skuLabels = computed(() => skus.value.map((s) => s.display_label || s.name || s.code || String(s.id)))
const productLabels = computed(() => products.value.map((p) => p.display_name || p.name || p.code || String(p.id)))

onShow(async () => {
  if (!requirePermission('bom.manage')) return
  await loadOptions()
  await reload()
})

async function loadOptions() {
  try {
    const [mat, opt] = await Promise.all([masterAdminApi.listMaterials(), masterAdminApi.bomFormOptions()])
    materials.value = mat.items || []
    skus.value = opt.skus || []
    products.value = opt.products || []
  } catch {
    materials.value = []
  }
}

async function reload() {
  loading.value = true
  try {
    const r = await masterAdminApi.listBoms({ limit: 50, keyword: keyword.value.trim() || undefined })
    items.value = r.items || []
  } catch {
    items.value = []
  } finally {
    loading.value = false
  }
}

function onScopePick(e: { detail: { value: number } }) {
  scopeIndex.value = Number(e.detail.value)
  form.scope = scopes[scopeIndex.value]?.value || 'sku'
}
function onSkuPick(e: { detail: { value: number } }) { skuIndex.value = Number(e.detail.value) }
function onProductPick(e: { detail: { value: number } }) { productIndex.value = Number(e.detail.value) }
function onMaterialPick(idx: number, e: { detail: { value: number } }) {
  lines.value[idx].materialIndex = Number(e.detail.value)
  lines.value[idx].material_id = materials.value[lines.value[idx].materialIndex!]?.id
}
function addLine() { lines.value.push({ qty_per: '1', materialIndex: 0 }) }
function removeLine(idx: number) { if (lines.value.length > 1) lines.value.splice(idx, 1) }

function openCreate() {
  formMode.value = 'create'
  editingId.value = null
  scopeIndex.value = 2
  form.scope = 'sku'
  form.name = ''
  form.version = '1'
  form.remark = ''
  lines.value = [{ qty_per: '1', materialIndex: 0 }]
  formVisible.value = true
}

async function openEdit(row: BomOut) {
  formMode.value = 'edit'
  editingId.value = row.id
  try {
    const d = await masterAdminApi.getBom(row.id)
    form.scope = d.scope
    form.name = d.name || ''
    form.version = String(d.version ?? 1)
    form.remark = d.remark || ''
    scopeIndex.value = Math.max(0, scopes.findIndex((s) => s.value === d.scope))
    lines.value = (d.items || []).length
      ? d.items!.map((it) => ({
          id: it.id,
          material_id: it.material_id,
          materialIndex: Math.max(0, materials.value.findIndex((m) => m.id === it.material_id)),
          qty_per: String(it.qty_per),
          remark: it.remark || '',
        }))
      : [{ qty_per: '1', materialIndex: 0 }]
    formVisible.value = true
  } catch {
    uni.showToast({ title: '加载失败', icon: 'none' })
  }
}

function buildPayload() {
  const mapped = lines.value.map((ln) => {
    const mat = materials.value[ln.materialIndex ?? 0]
    if (!mat && !ln.material_id) throw new Error('请选择物料')
    const qty = Number(ln.qty_per)
    if (!(qty >= 0)) throw new Error('单耗须≥0')
    return { id: ln.id, material_id: ln.material_id || mat!.id, qty_per: qty, remark: ln.remark || null }
  })
  if (!mapped.length) throw new Error('请添加明细')
  const payload: Record<string, unknown> = {
    version: Number(form.version) || 1,
    remark: form.remark.trim() || null,
    items: mapped,
  }
  if (formMode.value === 'create') {
    payload.scope = form.scope
    if (form.scope === 'global') payload.name = form.name.trim() || null
    if (form.scope === 'sku') payload.sku_id = skus.value[skuIndex.value]?.id
    if (form.scope === 'product') payload.product_id = products.value[productIndex.value]?.id
  } else {
    payload.name = form.name.trim() || null
  }
  return payload
}

async function submit() {
  saving.value = true
  try {
    const payload = buildPayload()
    if (formMode.value === 'create') {
      await masterAdminApi.createBom(payload)
      uni.showToast({ title: '创建成功', icon: 'success' })
    } else if (editingId.value) {
      await masterAdminApi.updateBom(editingId.value, payload)
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

function disableBom() {
  if (!editingId.value) return
  uni.showModal({
    title: '停用BOM',
    content: '确认停用？',
    success: async (res) => {
      if (!res.confirm || !editingId.value) return
      await masterAdminApi.disableBom(editingId.value)
      uni.showToast({ title: '已停用', icon: 'success' })
      formVisible.value = false
      await reload()
    },
  })
}
</script>

<style scoped lang="scss">
.toolbar { display: flex; gap: 12rpx; margin-bottom: 20rpx; }
.search { flex: 1; background: #fff; border-radius: 999rpx; padding: 16rpx 28rpx; font-size: 26rpx; }
.add-btn { background: linear-gradient(135deg, #6366f1, #4338ca); color: #fff; border-radius: 999rpx; }
.mask { position: fixed; inset: 0; background: rgba(15,23,42,.45); z-index: 10000; display: flex; align-items: flex-end; }
.sheet { width: 100%; max-height: 85vh; background: #fff; border-radius: 24rpx 24rpx 0 0; }
.head { padding: 28rpx 32rpx; border-bottom: 1rpx solid #f1f5f9; }
.title { font-size: 32rpx; font-weight: 700; }
.body { max-height: 58vh; padding: 16rpx 32rpx; box-sizing: border-box; }
.field { margin-bottom: 20rpx; }
.label { display: block; font-size: 26rpx; color: #475569; margin-bottom: 8rpx; }
.input { background: #f8fafc; border-radius: 12rpx; padding: 20rpx; font-size: 28rpx; }
.area { min-height: 100rpx; width: 100%; }
.picker { color: #334155; }
.flex1 { flex: 1; }
.lines-head { display: flex; justify-content: space-between; margin: 12rpx 0; }
.link { color: #4338ca; font-size: 26rpx; }
.line-card { display: flex; gap: 8rpx; align-items: center; margin-bottom: 12rpx; }
.qty { width: 140rpx; flex-shrink: 0; }
.del { color: #ef4444; font-size: 24rpx; }
.foot { display: flex; gap: 12rpx; padding: 20rpx 32rpx calc(20rpx + env(safe-area-inset-bottom)); border-top: 1rpx solid #f1f5f9; }
.btn { flex: 1; border-radius: 12rpx; font-size: 26rpx; }
.ghost { background: #f1f5f9; color: #475569; }
.primary { background: linear-gradient(135deg, #6366f1, #4338ca); color: #fff; }
.danger { color: #ef4444; }
</style>
