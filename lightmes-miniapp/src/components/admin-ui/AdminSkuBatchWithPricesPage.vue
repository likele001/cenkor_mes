<template>
  <view class="adm-page">
    <view class="hint">选择产品后逐行填写型号及工序单价；同产品下已存在的型号名称将自动跳过。</view>

    <picker :range="productOptions" range-key="label" @change="onProductPick">
      <view class="picker">{{ selectedProductLabel || '选择产品' }}</view>
    </picker>
    <text v-if="routeHint" class="sub">{{ routeHint }}</text>
    <text v-if="existingHint" class="sub warn">{{ existingHint }}</text>

    <view v-if="loading" class="loading">加载中...</view>

    <view v-for="(model, midx) in models" :key="model._key" class="model-card">
      <view class="model-head">
        <text class="model-title">型号 {{ midx + 1 }}</text>
        <text v-if="models.length > 1" class="del" @tap="removeModel(midx)">删除</text>
      </view>
      <view class="field">
        <text class="label">名称 *</text>
        <input v-model="model.name" class="input" placeholder="型号名称" />
      </view>
      <view class="field">
        <text class="label">编码</text>
        <input v-model="model.code" class="input" placeholder="留空自动生成" />
      </view>
      <view class="field-row">
        <view class="field half">
          <text class="label">颜色</text>
          <input v-model="model.color" class="input" placeholder="可选" />
        </view>
        <view class="field half">
          <text class="label">材料</text>
          <input v-model="model.material" class="input" placeholder="可选" />
        </view>
      </view>
      <view class="field">
        <text class="label">规格</text>
        <input v-model="model.spec" class="input" placeholder="可选" />
      </view>

      <view class="price-title">工序工价（元/件）</view>
      <view v-for="proc in processes" :key="proc.process_id" class="price-row">
        <text class="proc-name">{{ proc.process_display_name || proc.process_name }}</text>
        <input v-model="model.prices[proc.process_id]" class="input sm" type="digit" placeholder="单价" />
      </view>
    </view>

    <button class="ghost" size="mini" :disabled="!productId" @tap="addModel">+ 添加一行型号</button>
    <button class="save" :loading="saving" :disabled="!productId || !processes.length" @tap="save">批量添加</button>
  </view>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { adminApi } from '@/api/admin'

type ProcessRow = {
  process_id: number
  process_name: string
  process_display_name?: string
}

type ModelRow = {
  _key: number
  code: string
  name: string
  color: string
  material: string
  spec: string
  prices: Record<number, string>
}

const productOptions = ref<{ id: number; label: string }[]>([])
const productId = ref<number | null>(null)
const processes = ref<ProcessRow[]>([])
const existingNames = ref<string[]>([])
const routeHint = ref('')
const loading = ref(false)
const saving = ref(false)
const models = ref<ModelRow[]>([])
let modelKeySeq = 1

const selectedProductLabel = computed(
  () => productOptions.value.find((p) => p.id === productId.value)?.label || '',
)
const existingHint = computed(() =>
  existingNames.value.length ? `已有 ${existingNames.value.length} 个型号，重名将跳过` : '',
)

function emptyModel(): ModelRow {
  return {
    _key: modelKeySeq++,
    code: '',
    name: '',
    color: '',
    material: '',
    spec: '',
    prices: {},
  }
}

onMounted(async () => {
  const res = await adminApi.listProducts({ limit: 200, include_inactive: false })
  productOptions.value = (res.items || []).map((p: Record<string, unknown>) => ({
    id: Number(p.id),
    label: String(p.display_name || p.name || p.code || p.id),
  }))
  models.value = [emptyModel()]
})

function onProductPick(e: { detail: { value: string } }) {
  const idx = Number(e.detail.value)
  productId.value = productOptions.value[idx]?.id ?? null
  loadTemplate()
}

async function loadTemplate() {
  processes.value = []
  existingNames.value = []
  routeHint.value = ''
  models.value = [emptyModel()]
  if (!productId.value) return
  loading.value = true
  try {
    const tpl = await adminApi.getSkuBatchTemplate(productId.value)
    processes.value = (tpl.processes || []) as ProcessRow[]
    existingNames.value = (tpl.existing_names || []) as string[]
    routeHint.value = tpl.route_name
      ? `工艺路线：${tpl.route_name}`
      : tpl.route_source === 'all'
        ? '未配置默认工艺路线，显示全部启用工序'
        : ''
  } finally {
    loading.value = false
  }
}

function addModel() {
  models.value.push(emptyModel())
}

function removeModel(idx: number) {
  if (models.value.length <= 1) return
  models.value.splice(idx, 1)
}

async function save() {
  if (!productId.value) return
  const items = models.value
    .map((m) => ({
      code: m.code.trim() || null,
      name: m.name.trim(),
      color: m.color.trim() || null,
      material: m.material.trim() || null,
      spec: m.spec.trim() || null,
      is_active: true,
      prices: processes.value
        .map((p) => ({
          process_id: p.process_id,
          unit_price: String(m.prices[p.process_id] ?? '').trim() || null,
          is_active: true,
        }))
        .filter((x) => x.unit_price),
    }))
    .filter((x) => x.name)

  if (!items.length) {
    uni.showToast({ title: '请填写型号名称', icon: 'none' })
    return
  }

  saving.value = true
  try {
    const res = await adminApi.batchCreateSkusWithPrices({ product_id: productId.value, items })
    uni.showToast({
      title: `添加${res.added} 跳过${res.skipped}`,
      icon: 'success',
    })
    await loadTemplate()
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
.sub {
  display: block;
  font-size: 22rpx;
  color: #94a3b8;
  margin-bottom: 16rpx;
}
.sub.warn {
  color: #d97706;
}
.model-card {
  background: #fff;
  border-radius: 12rpx;
  padding: 20rpx;
  margin-bottom: 20rpx;
}
.model-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16rpx;
}
.model-title {
  font-weight: 600;
}
.field {
  margin-bottom: 12rpx;
}
.field-row {
  display: flex;
  gap: 12rpx;
}
.half {
  flex: 1;
}
.label {
  display: block;
  font-size: 22rpx;
  color: #64748b;
  margin-bottom: 6rpx;
}
.input {
  background: #f1f5f9;
  padding: 16rpx;
  border-radius: 8rpx;
}
.input.sm {
  flex: 1;
  min-width: 120rpx;
}
.price-title {
  font-size: 24rpx;
  color: #475569;
  margin: 16rpx 0 8rpx;
}
.price-row {
  display: flex;
  align-items: center;
  gap: 12rpx;
  margin-bottom: 10rpx;
}
.proc-name {
  width: 220rpx;
  font-size: 24rpx;
  flex-shrink: 0;
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
