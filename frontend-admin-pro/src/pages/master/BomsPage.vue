<template>
  <AdminPage :title="t('master.boms.title')" :description="t('master.boms.description')">
    <template #actions>
      <div class="flex items-center gap-2 flex-wrap">
          <el-select v-model="query.scope" clearable :placeholder="t('master.boms.scope')" style="width: 140px" @change="reload(true)">
            <el-option :label="t('master.boms.scopeSku')" value="sku" />
            <el-option :label="t('master.boms.scopeProduct')" value="product" />
            <el-option :label="t('master.boms.scopeGlobal')" value="global" />
          </el-select>
          <el-input v-model="query.keyword" :placeholder="t('master.boms.searchPlaceholder')" clearable style="width: 180px" @keyup.enter="reload(true)" />
          <el-button :loading="exporting" @click="exportExcel">导出 Excel</el-button>
          <el-button type="primary" @click="openCreate">{{ t('master.boms.add') }}</el-button>
        </div>
    </template>

    <div class="mt-4" v-loading="loading">
        <el-table class="hidden lg:block w-full" :data="items" border>
          <el-table-column prop="id" :label="t('master.common.id')" width="80" />
          <el-table-column :label="t('master.boms.scope')" width="110">
            <template #default="{ row }">
              <el-tag size="small" :type="scopeTagType(row.scope)">{{ row.scope_label || row.scope }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column :label="t('master.boms.scopeRange')" min-width="260">
            <template #default="{ row }">
              <template v-if="row.scope === 'global'">
                <div class="font-medium">{{ row.name || t('master.boms.scopeGlobal') }}</div>
              </template>
              <template v-else-if="row.scope === 'product'">
                <div class="font-medium">{{ row.product_name || row.name }}</div>
                <div class="text-xs text-zinc-500">{{ row.product_code }}</div>
              </template>
              <template v-else>
                <div class="font-medium">{{ row.sku_name || row.name }}</div>
                <div class="text-xs text-zinc-500">{{ row.sku_code }}</div>
              </template>
            </template>
          </el-table-column>
          <el-table-column prop="version" :label="t('master.boms.version')" width="80" />
          <el-table-column prop="remark" :label="t('master.boms.remark')" min-width="180" show-overflow-tooltip />
          <el-table-column :label="t('master.boms.operation')" width="280" fixed="right">
            <template #default="{ row }">
              <el-button size="small" @click="openEdit(row)">{{ t('master.boms.edit') }}</el-button>
              <el-button v-if="row.scope !== 'sku'" size="small" @click="openCopy(row)">{{ t('master.boms.copyToSku') }}</el-button>
              <el-popconfirm :title="t('master.boms.confirmDisable')" @confirm="onDisable(row)">
                <template #reference>
                  <el-button size="small" type="danger" :disabled="!row.is_active">{{ t('master.boms.disable') }}</el-button>
                </template>
              </el-popconfirm>
            </template>
          </el-table-column>
        </el-table>
      </div>

    <template #extra>
      <el-dialog v-model="dlg.open" :title="dlg.id ? t('master.boms.editTitle') : t('master.boms.addTitle')" width="980px" destroy-on-close>
            <el-form :model="dlg.form" label-width="100px">
              <el-form-item v-if="!dlg.id" :label="t('master.boms.scopeLabel')">
                <el-radio-group v-model="dlg.form.scope">
                  <el-radio value="global">{{ t('master.boms.scopeGlobalDesc') }}</el-radio>
                  <el-radio value="product">{{ t('master.boms.scopeProductDesc') }}</el-radio>
                  <el-radio value="sku">{{ t('master.boms.scopeSkuDesc') }}</el-radio>
                </el-radio-group>
              </el-form-item>
              <el-form-item v-if="dlg.form.scope === 'global'" :label="t('master.boms.templateName')">
                <el-input v-model="dlg.form.name" :placeholder="t('master.boms.templateNamePlaceholder')" />
              </el-form-item>
              <el-form-item v-if="dlg.form.scope === 'product' && !dlg.id" :label="t('master.boms.product')">
                <el-select v-model="dlg.form.product_id" filterable :placeholder="t('master.boms.selectProduct')" style="width: 100%">
                  <el-option v-for="p in products" :key="p.id" :label="productOptionLabel(p)" :value="p.id" />
                </el-select>
              </el-form-item>
              <el-form-item v-if="dlg.form.scope === 'sku' && !dlg.id" :label="t('master.boms.sku')">
                <el-select v-model="dlg.form.sku_id" filterable :placeholder="t('master.boms.selectSku')" style="width: 100%">
                  <el-option v-for="s in skus" :key="s.id" :label="skuOptionLabel(s)" :value="s.id">
                    <div class="leading-tight py-0.5">
                      <div>{{ skuOptionLabel(s) }}</div>
                      <div class="text-xs text-zinc-400">{{ skuOptionSubline(s) }}</div>
                    </div>
                  </el-option>
                </el-select>
              </el-form-item>
              <el-row :gutter="12">
                <el-col :span="8">
                  <el-form-item :label="t('master.boms.version')">
                    <el-input-number v-model="dlg.form.version" :min="1" :controls="false" style="width: 100%" />
                  </el-form-item>
                </el-col>
                <el-col :span="8">
                  <el-form-item :label="t('master.boms.enable')">
                    <el-switch v-model="dlg.form.is_active" />
                  </el-form-item>
                </el-col>
              </el-row>
              <el-form-item :label="t('master.boms.remark')">
                <el-input v-model="dlg.form.remark" type="textarea" :rows="2" />
              </el-form-item>
            </el-form>

            <div class="mt-2 border rounded">
              <div class="px-3 py-2 border-b bg-zinc-50 flex items-center justify-between">
                <div class="font-medium">{{ t('master.boms.detailTitle') }}</div>
                <el-button size="small" type="primary" @click="addRow">{{ t('master.boms.addRow') }}</el-button>
              </div>
              <el-table :data="dlg.form.items" border>
                <el-table-column :label="t('master.boms.detailMaterial')" min-width="360">
                  <template #default="{ row }">
                    <el-select v-model="row.material_id" filterable :placeholder="t('master.boms.selectMaterial')" style="width: 100%">
                      <el-option v-for="m in materials" :key="m.id" :label="materialOptionLabel(m)" :value="m.id">
                        <div class="leading-tight py-0.5">
                          <div>{{ materialOptionLabel(m) }}</div>
                          <div class="text-xs text-zinc-400">{{ materialOptionSubline(m) }}</div>
                        </div>
                      </el-option>
                    </el-select>
                  </template>
                </el-table-column>
                <el-table-column :label="t('master.boms.detailQtyPerUnit')" width="140">
                  <template #default="{ row }">
                    <el-input-number v-model="row.qty_per" :min="0" :controls="false" style="width: 100%" />
                  </template>
                </el-table-column>
                <el-table-column :label="t('master.boms.detailRemark')" min-width="180">
                  <template #default="{ row }">
                    <el-input v-model="row.remark" />
                  </template>
                </el-table-column>
                <el-table-column label="" width="80">
                  <template #default="{ $index }">
                    <el-button size="small" type="danger" @click="removeRow($index)">{{ t('master.boms.detailDelete') }}</el-button>
                  </template>
                </el-table-column>
              </el-table>
            </div>

            <template #footer>
              <el-button @click="dlg.open = false">{{ t('master.common.cancel') }}</el-button>
              <el-button type="primary" :loading="dlg.saving" @click="onSave">{{ t('master.common.save') }}</el-button>
            </template>
          </el-dialog>

      <el-dialog v-model="copyDlg.open" :title="t('master.boms.copyTitle')" width="560px">
            <p class="text-sm text-zinc-600 mb-3">{{ t('master.boms.copyDesc', { source: copyDlg.sourceLabel }) }}</p>
            <el-form label-width="88px">
              <el-form-item v-if="!copyDlg.productId" :label="t('master.boms.belongingProduct')">
                <el-select
                  v-model="copyDlg.filterProductId"
                  filterable
                  clearable
                  :placeholder="t('master.boms.selectProductFirst')"
                  style="width: 100%"
                  @change="copyDlg.sku_id = null"
                >
                  <el-option v-for="p in products" :key="p.id" :label="productOptionLabel(p)" :value="p.id" />
                </el-select>
              </el-form-item>
              <el-form-item :label="t('master.boms.targetSku')">
                <el-select
                  v-model="copyDlg.sku_id"
                  filterable
                  :disabled="!copyDlg.productId && !copyDlg.filterProductId"
                  :placeholder="t('master.boms.selectTargetSku')"
                  style="width: 100%"
                >
                  <el-option v-for="s in copyTargetSkus" :key="s.id" :label="skuOptionLabel(s)" :value="s.id">
                    <div class="leading-tight py-0.5">
                      <div class="font-medium">{{ skuOptionLabel(s) }}</div>
                      <div class="text-xs text-zinc-400">{{ skuOptionSubline(s) }}</div>
                    </div>
                  </el-option>
                </el-select>
              </el-form-item>
            </el-form>
            <p v-if="copyFilterProductId && !copyTargetSkus.length" class="text-xs text-amber-600 mt-1">
              {{ t('master.boms.noSkuHint') }}
            </p>
            <template #footer>
              <el-button @click="copyDlg.open = false">{{ t('master.common.cancel') }}</el-button>
              <el-button type="primary" :loading="copyDlg.saving" @click="onCopyConfirm">{{ t('master.boms.confirmCopy') }}</el-button>
            </template>
          </el-dialog>
    </template>
  </AdminPage>
</template>

<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import AdminPage from '@/components/admin/AdminPage.vue'
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { materialsApi, type BomOut, type BomProductOption, type BomScope, type BomSkuOption, type MaterialOut } from '@/api/materials'
import { masterSkuOptionLabel, masterSkuOptionSubline, materialOptionLabel, materialOptionSubline } from '@/utils/display'

const { t } = useI18n()

type BomItemForm = { material_id: number | null; qty_per: number; remark: string }

const loading = ref(false)
const exporting = ref(false)
const items = ref<BomOut[]>([])
const skus = ref<BomSkuOption[]>([])
const products = ref<BomProductOption[]>([])
const materials = ref<MaterialOut[]>([])

const query = reactive({
  keyword: '',
  scope: '' as BomScope | '',
  offset: 0,
  limit: 50,
})

const dlg = reactive({
  open: false,
  id: null as number | null,
  saving: false,
  form: {
    scope: 'global' as BomScope,
    sku_id: null as number | null,
    product_id: null as number | null,
    name: '',
    version: 1,
    remark: '',
    is_active: true,
    items: [] as BomItemForm[],
  },
})

const copyDlg = reactive({
  open: false,
  bomId: 0,
  sourceLabel: '',
  productId: null as number | null,
  filterProductId: null as number | null,
  sku_id: null as number | null,
  saving: false,
})

const copyFilterProductId = computed(() => copyDlg.productId || copyDlg.filterProductId)

const copyTargetSkus = computed(() => {
  const pid = copyFilterProductId.value
  if (pid) return skus.value.filter((s) => s.product_id === pid)
  return skus.value
})

function productOptionLabel(p: BomProductOption) {
  return p.display_name || p.name || p.code
}

function skuOptionLabel(s: BomSkuOption) {
  return masterSkuOptionLabel(s)
}

function skuOptionSubline(s: BomSkuOption) {
  return masterSkuOptionSubline(s)
}

function scopeTagType(scope: string) {
  if (scope === 'global') return 'warning'
  if (scope === 'product') return 'success'
  return ''
}

async function loadMeta() {
  const [bomMeta, mRes] = await Promise.all([
    materialsApi.getBomFormOptions(),
    materialsApi.listMaterials({ keyword: '', offset: 0, limit: 200, include_inactive: false }),
  ])
  skus.value = bomMeta.skus || []
  products.value = bomMeta.products || []
  materials.value = mRes.items
}

async function reload(reset = false) {
  if (reset) query.offset = 0
  loading.value = true
  try {
    const res = await materialsApi.listBoms({
      keyword: query.keyword || undefined,
      scope: query.scope || undefined,
      offset: query.offset,
      limit: query.limit,
    })
    items.value = res.items
  } finally {
    loading.value = false
  }
}

function addRow() {
  dlg.form.items.push({ material_id: null, qty_per: 0, remark: '' })
}

function removeRow(i: number) {
  dlg.form.items.splice(i, 1)
}

function openCreate() {
  dlg.id = null
  dlg.form = {
    scope: 'global',
    sku_id: null,
    product_id: null,
    name: '沙发通用默认BOM',
    version: 1,
    remark: '',
    is_active: true,
    items: [{ material_id: null, qty_per: 0, remark: '' }],
  }
  dlg.open = true
}

async function openEdit(row: BomOut) {
  const data = await materialsApi.getBom(row.id)
  dlg.id = data.id
  dlg.form = {
    scope: data.scope,
    sku_id: data.sku_id,
    product_id: data.product_id,
    name: data.name || '',
    version: data.version,
    remark: data.remark || '',
    is_active: data.is_active,
    items: (data.items || []).map((x) => ({ material_id: x.material_id, qty_per: x.qty_per, remark: x.remark || '' })),
  }
  if (dlg.form.items.length === 0) addRow()
  dlg.open = true
}

function openCopy(row: BomOut) {
  copyDlg.bomId = row.id
  if (row.scope === 'product') {
    copyDlg.sourceLabel = `${row.product_name || row.name || t('master.boms.product')}（${t('master.boms.scopeProduct')} BOM）`
    copyDlg.productId = row.product_id
  } else {
    copyDlg.sourceLabel = row.scope === 'global' ? (row.name || t('master.boms.scopeGlobal') + ' BOM') : row.scope_label || row.name || String(row.id)
    copyDlg.productId = null
  }
  copyDlg.filterProductId = copyDlg.productId
  copyDlg.sku_id = null
  copyDlg.open = true
}

async function onCopyConfirm() {
  if (!copyDlg.productId && !copyDlg.filterProductId) {
    ElMessage.error(t('master.boms.pleaseSelectProduct'))
    return
  }
  if (!copyDlg.sku_id) {
    ElMessage.error(t('master.boms.pleaseSelectSku'))
    return
  }
  copyDlg.saving = true
  try {
    await materialsApi.copyBomToSku(copyDlg.bomId, copyDlg.sku_id)
    copyDlg.open = false
    ElMessage.success(t('master.boms.copySuccess'))
    await reload(false)
  } finally {
    copyDlg.saving = false
  }
}

async function onSave() {
  const rows = dlg.form.items
    .filter((x) => x.material_id)
    .map((x) => ({
      material_id: x.material_id as number,
      qty_per: Math.max(0, Number(x.qty_per || 0)),
      remark: x.remark ? x.remark : null,
    }))
  if (rows.length === 0) {
    ElMessage.error(t('master.boms.atLeastOneMaterial'))
    return
  }
  if (!dlg.id) {
    if (dlg.form.scope === 'sku' && !dlg.form.sku_id) {
      ElMessage.error(t('master.boms.pleaseSelectSku'))
      return
    }
    if (dlg.form.scope === 'product' && !dlg.form.product_id) {
      ElMessage.error(t('master.boms.pleaseSelectProduct'))
      return
    }
    if (dlg.form.scope === 'global' && !dlg.form.name?.trim()) {
      ElMessage.error(t('master.boms.pleaseInputTemplateName'))
      return
    }
  }

  dlg.saving = true
  try {
    const payload = {
      version: dlg.form.version,
      remark: dlg.form.remark || null,
      is_active: dlg.form.is_active,
      items: rows,
    }
    if (!dlg.id) {
      await materialsApi.createBom({
        scope: dlg.form.scope,
        sku_id: dlg.form.sku_id || undefined,
        product_id: dlg.form.product_id || undefined,
        name: dlg.form.name || null,
        version: dlg.form.version,
        remark: dlg.form.remark || null,
        is_default: dlg.form.scope === 'global',
        items: rows,
      })
    } else {
      await materialsApi.updateBom(dlg.id, { ...payload, name: dlg.form.name || null })
    }
    dlg.open = false
    await reload(false)
  } finally {
    dlg.saving = false
  }
}

async function onDisable(row: BomOut) {
  await materialsApi.disableBom(row.id)
  await reload(false)
}

async function exportExcel() {
  if (exporting.value) return
  exporting.value = true
  try {
    const blob = await materialsApi.exportBoms({})
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `boms_${new Date().toISOString().slice(0, 10)}.xlsx`
    a.click()
    URL.revokeObjectURL(url)
    ElMessage.success('导出成功')
  } catch { /* http 已提示 */
  } finally { exporting.value = false }
}

onMounted(async () => {
  await loadMeta()
  await reload(true)
})
</script>
