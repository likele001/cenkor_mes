<template>
  <AdminPage :title="t('master.skuBatch.title')">
      <div class="flex items-center justify-between gap-3 flex-wrap mb-4">
        <div>
          <div class="text-[16px] font-semibold">{{ t('master.skuBatch.title') }}</div>
          <div class="text-sm text-zinc-500 mt-1">{{ t('master.skuBatch.subtitle') }}</div>
        </div>
        <el-button @click="router.push({ name: 'master-skus' })">{{ t('master.skuBatch.returnToList') }}</el-button>
      </div>

      <el-form inline class="mb-4">
        <el-form-item :label="t('master.skuBatch.product')" required>
          <el-select
            v-model="productId"
            filterable
            clearable
            :placeholder="t('master.skuBatch.selectProduct')"
            style="width: 320px"
            @change="onProductChange"
          >
            <el-option v-for="p in products" :key="p.id" :label="productOptionLabel(p)" :value="p.id" />
          </el-select>
        </el-form-item>
        <el-form-item v-if="routeHint">
          <span class="text-sm text-zinc-500">{{ routeHint }}</span>
        </el-form-item>
      </el-form>

      <el-alert
        v-if="existingNames.length"
        class="mb-4"
        type="warning"
        :closable="false"
        :title="t('master.skuBatch.existingNamesHint', { count: existingNames.length })"
        :description="existingNames.slice(0, 8).join('、') + (existingNames.length > 8 ? '…' : '')"
      />

      <div v-loading="loadingTemplate" class="space-y-4">
        <div
          v-for="(model, idx) in models"
          :key="model._key"
          class="border border-zinc-200 rounded-lg p-4 bg-zinc-50/50"
        >
          <div class="flex items-center justify-between mb-3">
            <div class="font-medium text-zinc-700">{{ t('master.skuBatch.modelIndex', { index: idx + 1 }) }}</div>
            <el-button link type="danger" :disabled="models.length <= 1" @click="removeModel(idx)">{{ t('master.skuBatch.delete') }}</el-button>
          </div>

          <el-form inline class="flex flex-wrap gap-x-4 gap-y-2 mb-3">
            <el-form-item :label="t('master.skuBatch.name')" required>
              <el-input v-model="model.name" :placeholder="t('master.skuBatch.namePlaceholder')" style="width: 180px" />
            </el-form-item>
            <el-form-item :label="t('master.skuBatch.code')">
              <el-input v-model="model.code" :placeholder="t('master.skuBatch.codePlaceholder')" style="width: 160px" />
            </el-form-item>
            <el-form-item :label="t('master.skuBatch.color')">
              <el-input v-model="model.color" :placeholder="t('master.skuBatch.colorPlaceholder')" style="width: 120px" />
            </el-form-item>
            <el-form-item :label="t('master.skuBatch.material')">
              <el-input v-model="model.material" :placeholder="t('master.skuBatch.materialPlaceholder')" style="width: 140px" />
            </el-form-item>
            <el-form-item :label="t('master.skuBatch.spec')">
              <el-input v-model="model.spec" :placeholder="t('master.skuBatch.specPlaceholder')" style="width: 160px" />
            </el-form-item>
            <el-form-item :label="t('master.skuBatch.remark')">
              <el-input v-model="model.remark" :placeholder="t('master.skuBatch.remarkPlaceholder')" style="width: 180px" />
            </el-form-item>
          </el-form>

          <div class="text-sm text-zinc-600 mb-2">{{ t('master.skuBatch.processPrice') }}</div>
          <el-table :data="processes" border size="small" max-height="280">
            <el-table-column :label="t('master.skuBatch.process')" min-width="160">
              <template #default="{ row }">
                {{ row.process_display_name || row.process_name }}
              </template>
            </el-table-column>
            <el-table-column :label="t('master.skuBatch.unitPrice')" width="160">
              <template #default="{ row }">
                <el-input v-model="model.prices[row.process_id]" placeholder="0.00" />
              </template>
            </el-table-column>
          </el-table>
        </div>

        <el-empty v-if="productId && !loadingTemplate && !processes.length" :description="t('master.skuBatch.noProcessHint')" />

        <div class="flex items-center gap-3 flex-wrap">
          <el-button plain :disabled="!productId" @click="addModel">{{ t('master.skuBatch.addModel') }}</el-button>
          <el-button type="primary" :loading="saving" :disabled="!productId || !processes.length" @click="onSubmit">
            {{ t('master.skuBatch.batchAdd') }}
          </el-button>
        </div>
      </div>
  </AdminPage>
</template>

<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import AdminPage from '@/components/admin/AdminPage.vue'
import { onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { masterApi, type ProductOut, type SkuBatchProcessOut } from '@/api/master'
import { productOptionLabel } from '@/utils/display'
import { previewNextCode } from '@/utils/code'

const { t } = useI18n()

type ModelRow = {
  _key: number
  code: string
  name: string
  color: string
  material: string
  spec: string
  remark: string
  prices: Record<number, string>
}

const router = useRouter()
const route = useRoute()

const products = ref<ProductOut[]>([])
const productId = ref<number | null>(null)
const processes = ref<SkuBatchProcessOut[]>([])
const existingNames = ref<string[]>([])
const routeHint = ref('')
const loadingTemplate = ref(false)
const saving = ref(false)
const models = ref<ModelRow[]>([])
let modelKeySeq = 1

function emptyModel(): ModelRow {
  return {
    _key: modelKeySeq++,
    code: '',
    name: '',
    color: '',
    material: '',
    spec: '',
    remark: '',
    prices: {},
  }
}

function addModel() {
  models.value.push(emptyModel())
}

function removeModel(idx: number) {
  if (models.value.length <= 1) return
  models.value.splice(idx, 1)
}

async function loadProducts() {
  const res = await masterApi.listProducts({ offset: 0, limit: 200, include_inactive: false })
  products.value = res.items
}

async function onProductChange() {
  processes.value = []
  existingNames.value = []
  routeHint.value = ''
  models.value = [emptyModel()]
  if (!productId.value) return

  loadingTemplate.value = true
  try {
    const tpl = await masterApi.getSkuBatchTemplate(productId.value)
    processes.value = tpl.processes
    existingNames.value = tpl.existing_names || []
    routeHint.value = tpl.route_name
      ? `${t('master.processPrices.routeLabel')}${tpl.route_name}`
      : tpl.route_source === 'all'
        ? t('master.processPrices.noRouteHint')
        : ''
    const code = await previewNextCode('sku')
    models.value[0].code = code
  } finally {
    loadingTemplate.value = false
  }
}

async function onSubmit() {
  if (!productId.value) {
    ElMessage.warning(t('master.skuBatch.pleaseSelectProduct'))
    return
  }
  const items = models.value
    .map((m) => ({
      code: m.code.trim() || null,
      name: m.name.trim(),
      color: m.color.trim() || null,
      material: m.material.trim() || null,
      spec: m.spec.trim() || null,
      remark: m.remark.trim() || null,
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
    ElMessage.warning(t('master.skuBatch.pleaseInputModelName'))
    return
  }

  saving.value = true
  try {
    const res = await masterApi.batchCreateSkusWithPrices({ product_id: productId.value, items })
    const msg = t('master.skuBatch.addSuccess', { added: res.added })
      + (res.skipped ? t('master.skuBatch.skipHint', { skipped: res.skipped }) : '')
      + t('master.skuBatch.priceHint', { pricesCreated: res.prices_created, pricesUpdated: res.prices_updated })
    ElMessage.success(msg)
    await onProductChange()
  } finally {
    saving.value = false
  }
}

onMounted(async () => {
  await loadProducts()
  const pid = route.query.product_id
  if (pid) {
    productId.value = Number(pid)
    await onProductChange()
  } else if (!models.value.length) {
    models.value = [emptyModel()]
  }
})
</script>
