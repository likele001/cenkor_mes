<template>
  <view class="adm-page">
    <view class="hint">选择型号后，按产品工艺路线列出各工序，填写单价后一次保存。</view>

    <picker :range="skuOptions" range-key="label" @change="onSkuPick">
      <view class="picker">{{ selectedSkuLabel || '选择型号' }}</view>
    </picker>
    <text v-if="routeHint" class="sub">{{ routeHint }}</text>

    <view v-if="loading" class="loading">加载中...</view>
    <view v-for="(row, idx) in rows" :key="idx" class="row-card">
      <view v-if="row._picker" class="row-head">
        <picker :range="processOptions(idx)" range-key="label" @change="(e) => onProcessPick(idx, e)">
          <view class="picker sm">选择工序</view>
        </picker>
      </view>
      <view v-else class="row-head">{{ row.process_display_name || row.process_name }}</view>
      <view class="row-fields">
        <input v-model="row.unit_price" class="input" type="digit" placeholder="单价(元/件)" />
        <label class="switch-line">
          <switch :checked="row.is_active" @change="(e) => (row.is_active = e.detail.value)" />
          <text>启用</text>
        </label>
        <text class="del" @tap="rows.splice(idx, 1)">删除</text>
      </view>
    </view>

    <button class="ghost" size="mini" @tap="addRow">+ 增加行</button>
    <button class="save" :loading="saving" :disabled="!skuId" @tap="save">保存全部工价</button>
  </view>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { adminApi } from '@/api/admin'

type Row = {
  process_id: number | null
  process_name?: string
  process_display_name?: string
  unit_price: string
  is_active: boolean
  _picker?: boolean
}

const skuOptions = ref<{ id: number; label: string }[]>([])
const processList = ref<{ id: number; name: string; display_name?: string; code?: string }[]>([])
const skuId = ref<number | null>(null)
const rows = ref<Row[]>([])
const loading = ref(false)
const saving = ref(false)
const routeHint = ref('')

const selectedSkuLabel = computed(() => skuOptions.value.find((s) => s.id === skuId.value)?.label || '')

function processOptions(rowIdx: number) {
  const used = new Set(
    rows.value.filter((r, i) => i !== rowIdx && r.process_id).map((r) => r.process_id!),
  )
  return processList.value
    .filter((p) => !used.has(p.id))
    .map((p) => ({ id: p.id, label: p.display_name || p.name || p.code || String(p.id) }))
}

onMounted(async () => {
  const [skus, procs] = await Promise.all([
    adminApi.listSkus({ limit: 200, include_inactive: false }),
    adminApi.listProcesses({ limit: 200, include_inactive: false }),
  ])
  skuOptions.value = (skus.items || []).map((s: Record<string, unknown>) => ({
    id: Number(s.id),
    label: String(s.display_label || s.name || s.code || s.id),
  }))
  processList.value = (procs.items || []) as typeof processList.value
})

function onSkuPick(e: { detail: { value: string } }) {
  const idx = Number(e.detail.value)
  skuId.value = skuOptions.value[idx]?.id ?? null
  loadMatrix()
}

async function loadMatrix() {
  if (!skuId.value) return
  loading.value = true
  try {
    const res = await adminApi.getPriceMatrix(skuId.value)
    routeHint.value = res.route_name ? `工艺路线：${res.route_name}` : '未配置默认工艺路线'
    rows.value = ((res.rows || []) as Record<string, unknown>[]).map((r) => ({
      process_id: Number(r.process_id),
      process_name: String(r.process_name || ''),
      process_display_name: String(r.process_display_name || r.process_name || ''),
      unit_price: r.unit_price != null ? String(r.unit_price) : '',
      is_active: r.is_active !== false,
    }))
    if (!rows.value.length) addRow()
  } finally {
    loading.value = false
  }
}

function addRow() {
  rows.value.push({ process_id: null, unit_price: '', is_active: true, _picker: true })
}

function onProcessPick(rowIdx: number, e: { detail: { value: string } }) {
  const opts = processOptions(rowIdx)
  const p = opts[Number(e.detail.value)]
  if (!p) return
  const full = processList.value.find((x) => x.id === p.id)
  rows.value[rowIdx].process_id = p.id
  rows.value[rowIdx].process_name = full?.name
  rows.value[rowIdx].process_display_name = full?.display_name || full?.name
  rows.value[rowIdx]._picker = false
}

async function save() {
  if (!skuId.value) return
  const items = rows.value
    .filter((r) => r.process_id && String(r.unit_price).trim())
    .map((r) => ({
      process_id: Number(r.process_id),
      unit_price: String(r.unit_price).trim(),
      is_active: r.is_active,
    }))
  if (!items.length) {
    uni.showToast({ title: '请填写至少一条单价', icon: 'none' })
    return
  }
  saving.value = true
  try {
    const res = await adminApi.batchSavePrices({ sku_id: skuId.value, items })
    uni.showToast({ title: `已保存 +${res.created} / 更新${res.updated}`, icon: 'success' })
  } finally {
    saving.value = false
  }
}
</script>

<style scoped lang="scss">
.hint {
  font-size: 24rpx;
  color: #64748b;
  margin-bottom: 16rpx;
}
.picker {
  background: #fff;
  padding: 24rpx;
  border-radius: 12rpx;
  margin-bottom: 12rpx;
}
.picker.sm {
  padding: 12rpx 0;
  background: transparent;
}
.sub {
  display: block;
  font-size: 22rpx;
  color: #94a3b8;
  margin-bottom: 16rpx;
}
.row-card {
  background: #fff;
  border-radius: 12rpx;
  padding: 20rpx;
  margin-bottom: 16rpx;
}
.row-head {
  font-weight: 600;
  margin-bottom: 12rpx;
}
.row-fields {
  display: flex;
  align-items: center;
  gap: 16rpx;
  flex-wrap: wrap;
}
.input {
  flex: 1;
  min-width: 160rpx;
  background: #f1f5f9;
  padding: 16rpx;
  border-radius: 8rpx;
}
.switch-line {
  display: flex;
  align-items: center;
  gap: 8rpx;
  font-size: 24rpx;
}
.del {
  color: #ef4444;
  font-size: 24rpx;
}
.ghost {
  margin: 12rpx 0 24rpx;
}
.save {
  background: #2563eb;
  color: #fff;
}
.loading {
  text-align: center;
  padding: 24rpx;
  color: #94a3b8;
}
</style>
