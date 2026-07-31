<template>
  <AdminPage :title="t('master.skus.title')">
    <el-card>
      <div class="flex items-center justify-between gap-3 flex-wrap">
        <div class="text-[16px] font-semibold">{{ t('master.skus.title') }}</div>
        <div class="flex items-center gap-2 flex-wrap justify-end">
          <el-select v-model="query.product_id" clearable filterable :placeholder="t('master.skus.product')" style="width: 220px" @change="reload(true)">
            <el-option v-for="p in products" :key="p.id" :label="productOptionLabel(p)" :value="p.id" />
          </el-select>
          <el-input v-model="query.keyword" :placeholder="t('master.skus.searchPlaceholder')" clearable style="width: 220px" @keyup.enter="reload(true)" />
          <el-switch v-model="query.include_inactive" :active-text="t('master.skus.includeDisabled')" @change="reload(true)" />
          <el-button type="primary" @click="openCreate">{{ t('master.skus.add') }}</el-button>
          <el-button type="success" plain @click="goBatch">{{ t('master.skus.batchAdd') }}</el-button>
          <el-button plain @click="openImport">{{ t('master.skus.importExcel') }}</el-button>
          <el-button :loading="exporting" @click="exportExcel">导出 Excel</el-button>
        </div>
      </div>

      <div class="mt-4" v-loading="loading">
        <el-table class="hidden lg:block w-full" :data="items" border>
          <el-table-column prop="id" :label="t('master.common.id')" width="90" />
          <el-table-column :label="t('master.skus.product')" width="260">
            <template #default="{ row }">
              <span>{{ productLabel(row.product_id) }}</span>
            </template>
          </el-table-column>
          <el-table-column prop="code" :label="t('master.skus.code')" width="180" />
          <el-table-column prop="name" :label="t('master.skus.name')" width="200" />
          <el-table-column prop="color" :label="t('master.skus.color')" width="140" />
          <el-table-column prop="material" :label="t('master.skus.material')" width="160" />
          <el-table-column prop="spec" :label="t('master.skus.spec')" width="180" />
          <el-table-column :label="t('master.skus.status')" width="120">
            <template #default="{ row }">
              <el-tag :type="row.is_active ? 'success' : 'info'">{{ row.is_active ? t('master.skus.enabled') : t('master.skus.disabled') }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column :label="t('master.skus.operation')" width="280" fixed="right">
            <template #default="{ row }">
              <el-button size="small" type="success" plain @click="goSetPrices(row)">{{ t('master.skus.setPrices') }}</el-button>
              <el-button size="small" @click="openEdit(row)">{{ t('master.skus.edit') }}</el-button>
              <el-popconfirm :title="t('master.skus.confirmDisable')" @confirm="onDisable(row)">
                <template #reference>
                  <el-button size="small" type="danger" :disabled="!row.is_active">{{ t('master.skus.disable') }}</el-button>
                </template>
              </el-popconfirm>
            </template>
          </el-table-column>
        </el-table>

        <div class="lg:hidden space-y-3">
          <div v-for="row in items" :key="row.id" class="admin-mobile-row">
            <div class="admin-mobile-row__head">
              <div class="min-w-0">
                <div class="font-semibold text-el-primary">{{ row.name }}</div>
                <div class="text-xs text-el-placeholder">{{ row.code }} · #{{ row.id }}</div>
              </div>
              <el-tag :type="row.is_active ? 'success' : 'info'" size="small">{{ row.is_active ? t('master.skus.enabled') : t('master.skus.disabled') }}</el-tag>
            </div>
            <dl class="admin-mobile-kv">
              <dt>{{ t('master.skus.product') }}</dt>
              <dd>{{ productLabel(row.product_id) }}</dd>
              <dt>{{ t('master.skus.color') }}</dt>
              <dd>{{ row.color || '—' }}</dd>
              <dt>{{ t('master.skus.material') }}</dt>
              <dd>{{ row.material || '—' }}</dd>
              <dt>{{ t('master.skus.spec') }}</dt>
              <dd>{{ row.spec || '—' }}</dd>
            </dl>
            <div class="admin-mobile-actions">
              <el-button size="small" type="success" plain @click="goSetPrices(row)">{{ t('master.skus.pricesBtn') }}</el-button>
              <el-button size="small" @click="openEdit(row)">{{ t('master.skus.edit') }}</el-button>
              <el-popconfirm :title="t('master.skus.confirmDisable')" @confirm="onDisable(row)">
                <template #reference>
                  <el-button size="small" type="danger" :disabled="!row.is_active">{{ t('master.skus.disable') }}</el-button>
                </template>
              </el-popconfirm>
            </div>
          </div>
          <el-empty v-if="!loading && !items.length" :description="t('master.skus.noData')" />
        </div>
      </div>

      <div class="mt-4 flex justify-end">
        <el-pagination
          background
          layout="prev, pager, next"
          :page-size="query.limit"
          :total="fakeTotal"
          :current-page="page"
          @current-change="onPageChange"
        />
      </div>
    </el-card>

    <el-dialog v-model="dlg.open" :title="dlg.id ? t('master.skus.editTitle') : t('master.skus.addTitle')" width="720px" destroy-on-close>
      <el-form ref="formRef" :model="dlg.form" :rules="rules" label-width="90px">
        <el-form-item :label="t('master.skus.product')" prop="product_id">
          <el-select v-model="dlg.form.product_id" filterable style="width: 100%">
            <el-option v-for="p in products" :key="p.id" :label="productOptionLabel(p)" :value="p.id" />
          </el-select>
        </el-form-item>
        <el-form-item :label="t('master.skus.code')" prop="code">
          <el-input v-model="dlg.form.code" :disabled="!!dlg.id" :placeholder="t('master.skus.autoGenerateHint')" clearable />
        </el-form-item>
        <el-form-item :label="t('master.skus.name')" prop="name">
          <el-input v-model="dlg.form.name" />
        </el-form-item>
        <el-form-item :label="t('master.skus.color')" prop="color">
          <el-input v-model="dlg.form.color" />
        </el-form-item>
        <el-form-item :label="t('master.skus.material')" prop="material">
          <el-input v-model="dlg.form.material" />
        </el-form-item>
        <el-form-item :label="t('master.skus.spec')" prop="spec">
          <el-input v-model="dlg.form.spec" />
        </el-form-item>
        <el-form-item :label="t('master.skus.remark')" prop="remark">
          <el-input v-model="dlg.form.remark" type="textarea" :rows="3" />
        </el-form-item>
        <el-form-item :label="t('master.skus.enable')" prop="is_active">
          <el-switch v-model="dlg.form.is_active" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dlg.open = false">{{ t('master.common.cancel') }}</el-button>
        <el-button type="primary" :loading="dlg.saving" @click="onSave">{{ t('master.common.save') }}</el-button>
      </template>
    </el-dialog>

    <!-- 导入 Excel -->
    <el-dialog v-model="importDlg.open" :title="t('master.skus.importTitle')" width="640px" destroy-on-close @closed="importDlg.result=null">
      <div v-if="!importDlg.result">
        <div class="mb-3 text-sm text-zinc-500">
          {{ t('master.skus.importHint') }}
        </div>
        <el-upload
          ref="uploadRef"
          drag
          accept=".xlsx,.xls"
          :auto-upload="false"
          :limit="1"
          :on-change="onImportFileChange"
          :on-exceed="() => {}"
        >
          <el-icon class="text-3xl"><UploadFilled /></el-icon>
          <div class="text-sm">{{ t('master.skus.importDragHint') }}<em>{{ t('master.skus.importClickSelect') }}</em></div>
        </el-upload>
      </div>

      <div v-if="importDlg.result" class="space-y-3">
        <el-alert
          :title="t('master.skus.importComplete', { success: importDlg.result.success, errors: importDlg.result.errors.length })"
          :type="importDlg.result.errors.length ? 'warning' : 'success'"
          show-icon
        />
        <div v-if="importDlg.result.errors.length" class="max-h-48 overflow-y-auto">
          <div v-for="e in importDlg.result.errors" :key="e.row" class="text-xs text-red-500 py-1">
            {{ t('master.skus.importRowError', { row: e.row, message: e.message }) }}
          </div>
        </div>
      </div>

      <template #footer>
        <el-button v-if="importDlg.result" @click="importDlg.open = false; reload(true)">{{ t('master.common.close') }}</el-button>
        <template v-else>
          <el-button @click="importDlg.open = false">{{ t('master.common.cancel') }}</el-button>
          <el-button type="primary" :loading="importDlg.uploading" :disabled="!importDlg.file" @click="onImportSubmit">
            {{ t('master.skus.importStart') }}
          </el-button>
        </template>
      </template>
    </el-dialog>  </AdminPage>
</template>

<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import AdminPage from '@/components/admin/AdminPage.vue'
import { computed, onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import type { FormInstance, FormRules, UploadInstance, UploadRawFile } from 'element-plus'
import { UploadFilled } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { masterApi, type ProductOut, type SkuOut } from '@/api/master'
import { productOptionLabel } from '@/utils/display'
import { codeForSubmit, previewNextCode } from '@/utils/code'

const { t } = useI18n()

const loading = ref(false)
const exporting = ref(false)
const items = ref<SkuOut[]>([])
const products = ref<ProductOut[]>([])
const query = reactive({ product_id: null as number | null, keyword: '', offset: 0, limit: 50, include_inactive: false })

const page = computed(() => Math.floor(query.offset / query.limit) + 1)
const fakeTotal = computed(() => query.offset + items.value.length + (items.value.length === query.limit ? query.limit : 0))

const dlg = reactive({
  open: false,
  id: null as number | null,
  saving: false,
  form: {
    product_id: null as number | null,
    code: '',
    name: '',
    color: '',
    material: '',
    spec: '',
    remark: '',
    is_active: true,
  },
})

const formRef = ref<FormInstance>()
const rules: FormRules = {
  product_id: [{ required: true, message: t('master.skus.pleaseSelectProduct'), trigger: 'change' }],
  name: [{ required: true, message: t('master.skus.pleaseInputName'), trigger: 'blur' }],
}

function productLabel(productId: number) {
  const p = products.value.find((x) => x.id === productId)
  return p ? productOptionLabel(p) : `${productId}`
}

async function loadProducts() {
  const res = await masterApi.listProducts({ offset: 0, limit: 200, include_inactive: true })
  products.value = res.items
}

async function reload(reset = false) {
  if (reset) query.offset = 0
  loading.value = true
  try {
    const res = await masterApi.listSkus({ ...query })
    items.value = res.items
  } finally {
    loading.value = false
  }
}

function onPageChange(p: number) {
  query.offset = (p - 1) * query.limit
  reload(false)
}

async function openCreate() {
  dlg.id = null
  dlg.form = {
    product_id: query.product_id,
    code: await previewNextCode('sku'),
    name: '',
    color: '',
    material: '',
    spec: '',
    remark: '',
    is_active: true,
  }
  dlg.open = true
}

function openEdit(row: SkuOut) {
  dlg.id = row.id
  dlg.form = {
    product_id: row.product_id,
    code: row.code,
    name: row.name,
    color: row.color || '',
    material: row.material || '',
    spec: row.spec || '',
    remark: row.remark || '',
    is_active: row.is_active,
  }
  dlg.open = true
}

const router = useRouter()
const route = useRoute()

function goSetPrices(row: SkuOut) {
  router.push({ name: 'master-process-prices', query: { sku_id: String(row.id), batch: '1' } })
}

function goBatch() {
  router.push({
    name: 'master-skus-batch',
    query: query.product_id ? { product_id: String(query.product_id) } : undefined,
  })
}

async function onSave() {
  const ok = await formRef.value?.validate().catch(() => false)
  if (!ok) return
  dlg.saving = true
  try {
    const payload = {
      product_id: dlg.form.product_id,
      code: dlg.id ? dlg.form.code : codeForSubmit(dlg.form.code),
      name: dlg.form.name,
      color: dlg.form.color || null,
      material: dlg.form.material || null,
      spec: dlg.form.spec || null,
      remark: dlg.form.remark || null,
      is_active: dlg.form.is_active,
    }
    if (!dlg.id) {
      const created = await masterApi.createSku(payload)
      dlg.open = false
      await reload(false)
      const go = await ElMessageBox.confirm(t('master.skus.saveConfirmMsg'), t('master.skus.saveConfirmTitle'), {
        confirmButtonText: t('master.skus.saveConfirmYes'),
        cancelButtonText: t('master.skus.saveConfirmNo'),
        type: 'info',
      })
        .then(() => true)
        .catch(() => false)
      if (go && created?.id) goSetPrices(created)
      return
    }
    await masterApi.updateSku(dlg.id, payload)
    dlg.open = false
    await reload(false)
  } finally {
    dlg.saving = false
  }
}

async function onDisable(row: SkuOut) {
  await masterApi.disableSku(row.id)
  await reload(false)
}

// ── 导入 Excel ──

const importDlg = reactive({
  open: false,
  file: null as File | null,
  uploading: false,
  result: null as { total: number; success: number; errors: { row: number; message: string }[] } | null,
})

function openImport() {
  importDlg.open = true
  importDlg.file = null
  importDlg.result = null
}

function onImportFileChange(uploadFile: any) {
  importDlg.file = uploadFile.raw as File
}

async function onImportSubmit() {
  if (!importDlg.file) {
    ElMessage.warning(t('master.skus.pleaseSelectFile'))
    return
  }
  importDlg.uploading = true
  try {
    importDlg.result = await masterApi.importSkus(importDlg.file)
  } finally {
    importDlg.uploading = false
  }
}

async function exportExcel() {
  if (exporting.value) return
  exporting.value = true
  try {
    const blob = await masterApi.exportSkus({})
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `skus_${new Date().toISOString().slice(0, 10)}.xlsx`
    a.click()
    URL.revokeObjectURL(url)
    ElMessage.success('导出成功')
  } catch { /* http 已提示 */
  } finally { exporting.value = false }
}

onMounted(async () => {
  await loadProducts()
  await reload(true)
  const pid = route.query.product_id
  if (route.query.create === '1' && pid) {
    query.product_id = Number(pid)
    await openCreate()
  }
})
</script>
