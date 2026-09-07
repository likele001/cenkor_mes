<template>
  <AdminPage :title="t('erp.assets.title')">
    <template #actions>
      <div class="flex items-center gap-2 flex-wrap">
        <el-select v-model="category" clearable :placeholder="t('erp.assets.category')" style="width:140px" @change="reload(true)">
          <el-option v-for="c in ['equipment','building','transport','office','other']" :key="c" :label="c" :value="c" />
        </el-select>
        <el-input v-model="keyword" :placeholder="t('erp.common.search')" style="width:160px" clearable @change="reload(true)" />
        <el-button type="primary" @click="openCreate">{{ t('erp.common.create') }}</el-button>
        <el-button @click="reload(true)">{{ t('erp.common.refresh') }}</el-button>
      </div>
    </template>

    <div class="mt-4" v-loading="loading">
      <el-table :data="items" border>
        <el-table-column prop="asset_no" :label="t('erp.assets.assetNo')" width="130" />
        <el-table-column prop="name" :label="t('erp.assets.name')" min-width="160" />
        <el-table-column prop="category" :label="t('erp.assets.category')" width="100" />
        <el-table-column prop="original_value" :label="t('erp.assets.original')" width="120" align="right">
          <template #default="{ row }">¥ {{ formatMoney(row.original_value) }}</template>
        </el-table-column>
        <el-table-column prop="accumulated_depreciation" :label="t('erp.assets.accumulated')" width="130" align="right">
          <template #default="{ row }">¥ {{ formatMoney(row.accumulated_depreciation) }}</template>
        </el-table-column>
        <el-table-column prop="book_value" :label="t('erp.assets.bookValue')" width="120" align="right">
          <template #default="{ row }"><b>¥ {{ formatMoney(row.book_value) }}</b></template>
        </el-table-column>
        <el-table-column prop="status" :label="t('erp.common.status')" width="90">
          <template #default="{ row }"><el-tag size="small">{{ row.status }}</el-tag></template>
        </el-table-column>
        <el-table-column :label="t('erp.common.actions')" width="140" align="center" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" @click="openEdit(row)">{{ t('erp.common.edit') }}</el-button>
            <el-button link type="danger" @click="remove(row)">{{ t('erp.common.delete') }}</el-button>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <el-dialog v-model="dialogVisible" :title="editingId ? t('erp.assets.edit') : t('erp.assets.create')" width="560px" destroy-on-close>
      <el-form :model="form" label-width="120px">
        <el-form-item :label="t('erp.assets.name')" required>
          <el-input v-model="form.name" />
        </el-form-item>
        <el-form-item :label="t('erp.assets.category')">
          <el-select v-model="form.category" style="width:100%">
            <el-option v-for="c in ['equipment','building','transport','office','other']" :key="c" :label="c" :value="c" />
          </el-select>
        </el-form-item>
        <el-form-item :label="t('erp.assets.original')">
          <el-input-number v-model="form.original_value" :precision="2" :controls="false" style="width:100%" />
        </el-form-item>
        <el-form-item :label="t('erp.assets.residual')">
          <el-input-number v-model="form.residual_value" :precision="2" :controls="false" style="width:100%" />
        </el-form-item>
        <el-form-item :label="t('erp.assets.lifeMonths')">
          <el-input-number v-model="form.useful_life_months" :min="1" :max="600" style="width:100%" />
        </el-form-item>
        <el-form-item :label="t('erp.assets.method')">
          <el-select v-model="form.depreciation_method" style="width:100%">
            <el-option label="straight_line" value="straight_line" />
            <el-option label="double_declining" value="double_declining" />
            <el-option label="sum_of_years" value="sum_of_years" />
          </el-select>
        </el-form-item>
        <el-form-item :label="t('erp.assets.purchaseDate')">
          <el-date-picker v-model="form.purchase_date" type="date" value-format="YYYY-MM-DD" style="width:100%" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">{{ t('erp.common.cancel') }}</el-button>
        <el-button type="primary" :loading="saving" @click="save">{{ t('erp.common.save') }}</el-button>
      </template>
    </el-dialog>
  </AdminPage>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { ElMessage, ElMessageBox } from 'element-plus'
import AdminPage from '@/components/admin/AdminPage.vue'
import { erpApi, type FixedAssetOut } from '@/api/erp'

const { t } = useI18n()
const loading = ref(false)
const saving = ref(false)
const items = ref<FixedAssetOut[]>([])
const category = ref('')
const keyword = ref('')
const dialogVisible = ref(false)
const editingId = ref<number | null>(null)
const form = reactive<any>({
  name: '', category: 'equipment', original_value: 0, residual_value: 0,
  useful_life_months: 60, depreciation_method: 'straight_line', purchase_date: '',
})

function formatMoney(v: number | undefined | null) {
  return (v ?? 0).toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

async function reload(_silent = false) {
  loading.value = true
  try {
    const resp = await erpApi.listAssets({ category: category.value || undefined, keyword: keyword.value || undefined, limit: 200 })
    items.value = resp?.items ?? []
  } catch (e: any) {
    ElMessage.error(e?.message || t('erp.common.loadFailed'))
  } finally {
    loading.value = false
  }
}

function openCreate() {
  editingId.value = null
  Object.assign(form, { name: '', category: 'equipment', original_value: 0, residual_value: 0, useful_life_months: 60, depreciation_method: 'straight_line', purchase_date: '' })
  dialogVisible.value = true
}

function openEdit(row: FixedAssetOut) {
  editingId.value = row.id
  Object.assign(form, {
    name: row.name, category: row.category, original_value: row.original_value,
    residual_value: row.residual_value, useful_life_months: row.useful_life_months,
    depreciation_method: row.depreciation_method, purchase_date: row.purchase_date || '',
  })
  dialogVisible.value = true
}

async function save() {
  saving.value = true
  try {
    const payload = { ...form }
    if (editingId.value) {
      await erpApi.updateAsset(editingId.value, payload)
    } else {
      await erpApi.createAsset(payload)
    }
    ElMessage.success(t('erp.common.saved'))
    dialogVisible.value = false
    reload(true)
  } catch (e: any) {
    ElMessage.error(e?.message || t('erp.common.saveFailed'))
  } finally {
    saving.value = false
  }
}

async function remove(row: FixedAssetOut) {
  await ElMessageBox.confirm(t('erp.common.confirmDelete'), '', { type: 'warning' })
  try {
    await erpApi.deleteAsset(row.id)
    ElMessage.success(t('erp.common.deleted'))
    reload(true)
  } catch (e: any) {
    ElMessage.error(e?.message)
  }
}

onMounted(() => reload(true))
</script>
