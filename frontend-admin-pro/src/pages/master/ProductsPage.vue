<template>
  <AdminPage :title="t('master.products.title')">
    <template #actions>
      <el-input v-model="query.keyword" :placeholder="t('master.products.searchPlaceholder')" clearable style="width: 220px" @keyup.enter="reload(true)" />
      <el-switch v-model="query.include_inactive" :active-text="t('master.products.includeDisabled')" @change="reload(true)" />
      <el-button :loading="exporting" @click="exportExcel">导出 Excel</el-button>
      <el-button type="primary" @click="openCreate">{{ t('master.products.add') }}</el-button>
    </template>

    <AdminDataTable
      :loading="loading"
      :empty="!loading && !items.length"
      :page-size="query.limit"
      :total="fakeTotal"
      :current-page="page"
      @page-change="onPageChangeHandler"
    >
      <template #table>
        <el-table class="hidden lg:block w-full" :data="items" border>
          <el-table-column prop="id" :label="t('master.common.id')" width="90" />
          <el-table-column prop="code" :label="t('master.products.code')" width="180" />
          <el-table-column :label="t('master.products.name')" min-width="200" show-overflow-tooltip>
            <template #default="{ row }">
              <div>{{ row.display_name || row.name }}</div>
              <div v-if="row.display_name && row.display_name !== row.name" class="text-xs text-[var(--admin-brand-subtitle)]">
                {{ t('master.products.itemNo') }} {{ row.name }}
              </div>
            </template>
          </el-table-column>
          <el-table-column prop="category" :label="t('master.products.category')" width="160" />
          <el-table-column prop="unit" :label="t('master.products.unit')" width="120" />
          <el-table-column prop="description" :label="t('master.products.description')" min-width="240" />
          <el-table-column :label="t('master.products.status')" width="120">
            <template #default="{ row }">
              <el-tag :type="row.is_active ? 'success' : 'info'">{{ row.is_active ? t('master.products.enabled') : t('master.products.disabled') }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column :label="t('master.products.operation')" width="220" fixed="right">
            <template #default="{ row }">
              <el-button size="small" @click="openEdit(row)">{{ t('master.products.edit') }}</el-button>
              <el-popconfirm :title="t('master.products.confirmDisable')" @confirm="onDisable(row)">
                <template #reference>
                  <el-button size="small" type="danger" :disabled="!row.is_active">{{ t('master.products.disable') }}</el-button>
                </template>
              </el-popconfirm>
            </template>
          </el-table-column>
        </el-table>
      </template>
      <template #mobile>
        <div class="lg:hidden space-y-3">
          <div v-for="row in items" :key="row.id" class="admin-mobile-row">
            <div class="admin-mobile-row__head">
              <div class="min-w-0">
                <div class="font-semibold text-[var(--el-text-color-primary)]">{{ row.name }}</div>
                <div class="text-xs text-[var(--admin-brand-subtitle)]">{{ row.code }} · #{{ row.id }}</div>
              </div>
              <el-tag :type="row.is_active ? 'success' : 'info'" size="small">{{ row.is_active ? t('master.products.enabled') : t('master.products.disabled') }}</el-tag>
            </div>
            <dl class="admin-mobile-kv">
              <dt>{{ t('master.products.category') }}</dt>
              <dd>{{ row.category || '—' }}</dd>
              <dt>{{ t('master.products.unit') }}</dt>
              <dd>{{ row.unit || '—' }}</dd>
              <dt>{{ t('master.products.description') }}</dt>
              <dd>{{ row.description || '—' }}</dd>
            </dl>
            <div class="admin-mobile-actions">
              <el-button size="small" @click="openEdit(row)">{{ t('master.products.edit') }}</el-button>
              <el-popconfirm :title="t('master.products.confirmDisable')" @confirm="onDisable(row)">
                <template #reference>
                  <el-button size="small" type="danger" :disabled="!row.is_active">{{ t('master.products.disable') }}</el-button>
                </template>
              </el-popconfirm>
            </div>
          </div>
        </div>
      </template>
    </AdminDataTable>

    <template #extra>
      <el-dialog v-model="dlg.open" :title="dlg.id ? t('master.products.editTitle') : t('master.products.addTitle')" width="640px" destroy-on-close>
        <el-form ref="formRef" :model="dlg.form" :rules="rules" label-width="90px">
          <el-form-item :label="t('master.products.code')" prop="code">
            <el-input v-model="dlg.form.code" :disabled="!!dlg.id" :placeholder="t('master.products.autoGenerateHint')" clearable />
          </el-form-item>
          <el-form-item :label="t('master.products.name')" prop="name">
            <el-input v-model="dlg.form.name" :placeholder="t('master.products.namePlaceholder')" />
          </el-form-item>
          <el-form-item :label="t('master.products.category')" prop="category">
            <el-input v-model="dlg.form.category" />
          </el-form-item>
          <el-form-item :label="t('master.products.unit')" prop="unit">
            <el-input v-model="dlg.form.unit" />
          </el-form-item>
          <el-form-item :label="t('master.products.description')" prop="description">
            <el-input
              v-model="dlg.form.description"
              type="textarea"
              :rows="4"
              :placeholder="t('master.products.descriptionPlaceholder')"
            />
          </el-form-item>
          <el-alert type="info" :closable="false" class="mb-2" :title="t('master.products.displayHintTitle')">
            {{ t('master.products.displayHint') }}
          </el-alert>
          <el-form-item :label="t('master.products.enable')" prop="is_active">
            <el-switch v-model="dlg.form.is_active" />
          </el-form-item>
        </el-form>
        <template #footer>
          <el-button @click="dlg.open = false">{{ t('master.common.cancel') }}</el-button>
          <el-button type="primary" :loading="dlg.saving" @click="onSave">{{ t('master.common.save') }}</el-button>
        </template>
      </el-dialog>
    </template>
  </AdminPage>
</template>

<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import { computed, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import type { FormInstance, FormRules } from 'element-plus'
import { ElMessage, ElMessageBox } from 'element-plus'
import AdminDataTable from '@/components/admin/AdminDataTable.vue'
import AdminPage from '@/components/admin/AdminPage.vue'
import { useListPage } from '@/composables/useListPage'
import { masterApi, type ProductOut } from '@/api/master'
import { codeForSubmit, previewNextCode } from '@/utils/code'

const { t } = useI18n()

const exporting = ref(false)
const items = ref<ProductOut[]>([])
const { loading, query, page, estimateTotal, onPageChange, runReload } = useListPage({
  keyword: '',
  offset: 0,
  limit: 50,
  include_inactive: false,
})

const fakeTotal = computed(() => estimateTotal(items.value.length))

const dlg = reactive({
  open: false,
  id: null as number | null,
  saving: false,
  form: { code: '', name: '', category: '', unit: '', description: '', is_active: true },
})

const formRef = ref<FormInstance>()
const router = useRouter()
const rules: FormRules = {
  name: [{ required: true, message: t('master.products.pleaseInputName'), trigger: 'blur' }],
}

async function reload(reset = false) {
  await runReload(reset, async (q) => {
    const res = await masterApi.listProducts({ ...q })
    items.value = res.items
  })
}

function onPageChangeHandler(p: number) {
  onPageChange(p)
  reload(false)
}

async function openCreate() {
  dlg.id = null
  dlg.form = { code: await previewNextCode('product'), name: '', category: '', unit: '', description: '', is_active: true }
  dlg.open = true
}

function openEdit(row: ProductOut) {
  dlg.id = row.id
  dlg.form = {
    code: row.code,
    name: row.name,
    category: row.category || '',
    unit: row.unit || '',
    description: row.description || '',
    is_active: row.is_active,
  }
  dlg.open = true
}

async function onSave() {
  const ok = await formRef.value?.validate().catch(() => false)
  if (!ok) return
  dlg.saving = true
  try {
    const payload = {
      code: dlg.id ? dlg.form.code : codeForSubmit(dlg.form.code),
      name: dlg.form.name,
      category: dlg.form.category || null,
      unit: dlg.form.unit || null,
      description: dlg.form.description || null,
      is_active: dlg.form.is_active,
    }
    if (!dlg.id) {
      const created = await masterApi.createProduct(payload)
      dlg.open = false
      await reload(false)
      const go = await ElMessageBox.confirm(t('master.products.saveConfirmMsg'), t('master.products.saveConfirmTitle'), {
        confirmButtonText: t('master.products.saveConfirmYes'),
        cancelButtonText: t('master.products.saveConfirmNo'),
        type: 'info',
      })
        .then(() => true)
        .catch(() => false)
      if (go && created?.id) {
        router.push({ name: 'master-skus', query: { product_id: String(created.id), create: '1' } })
      }
      return
    }
    await masterApi.updateProduct(dlg.id, payload)
    dlg.open = false
    await reload(false)
  } finally {
    dlg.saving = false
  }
}

async function onDisable(row: ProductOut) {
  await masterApi.disableProduct(row.id)
  await reload(false)
}

async function exportExcel() {
  if (exporting.value) return
  exporting.value = true
  try {
    const blob = await masterApi.exportProducts({})
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `products_${new Date().toISOString().slice(0, 10)}.xlsx`
    a.click()
    URL.revokeObjectURL(url)
    ElMessage.success('导出成功')
  } catch { /* http 已提示 */
  } finally { exporting.value = false }
}

onMounted(() => reload(true))
</script>
