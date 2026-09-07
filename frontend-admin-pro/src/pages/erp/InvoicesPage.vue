<template>
  <AdminPage :title="t('erp.invoices.title')">
    <template #actions>
      <div class="flex items-center gap-2 flex-wrap">
        <el-radio-group v-model="direction" @change="reload(true)">
          <el-radio-button value="out">{{ t('erp.invoices.out') }}</el-radio-button>
          <el-radio-button value="in">{{ t('erp.invoices.in') }}</el-radio-button>
        </el-radio-group>
        <el-select v-model="status" clearable :placeholder="t('erp.common.status')" style="width:120px" @change="reload(true)">
          <el-option label="draft" value="draft" />
          <el-option label="posted" value="posted" />
          <el-option label="void" value="void" />
        </el-select>
        <el-button type="primary" @click="openCreate">{{ t('erp.common.create') }}</el-button>
        <el-button @click="reload(true)">{{ t('erp.common.refresh') }}</el-button>
      </div>
    </template>

    <div class="mt-4" v-loading="loading">
      <el-table :data="items" border>
        <el-table-column prop="code" :label="t('erp.invoices.code')" width="130" />
        <el-table-column prop="invoice_no" :label="t('erp.invoices.invoiceNo')" min-width="140" />
        <el-table-column :label="t('erp.invoices.direction')" width="80">
          <template #default="{ row }">
            <el-tag :type="row.direction === 'out' ? 'danger' : 'success'" size="small">
              {{ row.direction === 'out' ? t('erp.invoices.out') : t('erp.invoices.in') }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="invoice_date" :label="t('erp.invoices.date')" width="110" />
        <el-table-column prop="total_amount" :label="t('erp.invoices.totalAmount')" width="120" align="right">
          <template #default="{ row }">¥ {{ formatMoney(row.total_amount) }}</template>
        </el-table-column>
        <el-table-column prop="status" :label="t('erp.common.status')" width="90">
          <template #default="{ row }"><el-tag size="small">{{ row.status }}</el-tag></template>
        </el-table-column>
        <el-table-column :label="t('erp.common.actions')" width="180" align="center" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" @click="view(row)">{{ t('erp.common.view') }}</el-button>
            <el-button v-if="row.status === 'draft'" link type="success" @click="post(row)">{{ t('erp.common.post') }}</el-button>
            <el-button v-if="row.status !== 'void'" link type="warning" @click="voidRow(row)">{{ t('erp.common.void') }}</el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-empty v-if="!loading && !items.length" :description="t('erp.common.empty')" />
    </div>

    <el-dialog v-model="dialogVisible" :title="editingId ? t('erp.invoices.edit') : t('erp.invoices.create')" width="640px" destroy-on-close>
      <el-form :model="form" label-width="110px">
        <el-form-item :label="t('erp.invoices.invoiceNo')">
          <el-input v-model="form.invoice_no" />
        </el-form-item>
        <el-form-item :label="t('erp.invoices.date')">
          <el-date-picker v-model="form.invoice_date" type="date" value-format="YYYY-MM-DD" />
        </el-form-item>
        <el-form-item :label="t('erp.invoices.amount')">
          <el-input-number v-model="form.amount" :precision="2" :controls="false" style="width:100%" />
        </el-form-item>
        <el-form-item :label="t('erp.invoices.taxRate')">
          <el-input-number v-model="form.tax_rate" :precision="2" :controls="false" style="width:100%" />
        </el-form-item>
        <el-form-item :label="t('erp.invoices.remark')">
          <el-input v-model="form.remark" type="textarea" :rows="2" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">{{ t('erp.common.cancel') }}</el-button>
        <el-button type="primary" :loading="saving" @click="save">{{ t('erp.common.save') }}</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="detailVisible" :title="t('erp.invoices.detail')" width="720px">
      <el-descriptions :column="2" border>
        <el-descriptions-item :label="t('erp.invoices.code')">{{ detail.code }}</el-descriptions-item>
        <el-descriptions-item :label="t('erp.invoices.invoiceNo')">{{ detail.invoice_no || '-' }}</el-descriptions-item>
        <el-descriptions-item :label="t('erp.invoices.date')">{{ detail.invoice_date }}</el-descriptions-item>
        <el-descriptions-item :label="t('erp.invoices.totalAmount')">¥ {{ formatMoney(detail.total_amount) }}</el-descriptions-item>
      </el-descriptions>
      <el-table :data="detail.items || []" border class="mt-3">
        <el-table-column prop="line_no" label="#" width="50" />
        <el-table-column prop="qty" label="Qty" width="80" />
        <el-table-column prop="unit_price" :label="t('erp.invoices.unitPrice')" width="110" />
        <el-table-column prop="total_amount" :label="t('erp.invoices.totalAmount')" width="120" />
      </el-table>
    </el-dialog>
  </AdminPage>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { ElMessage, ElMessageBox } from 'element-plus'
import AdminPage from '@/components/admin/AdminPage.vue'
import { erpApi, type InvoiceOut } from '@/api/erp'

const { t } = useI18n()
const loading = ref(false)
const saving = ref(false)
const items = ref<InvoiceOut[]>([])
const direction = ref('out')
const status = ref('')
const dialogVisible = ref(false)
const detailVisible = ref(false)
const editingId = ref<number | null>(null)
const detail = ref<any>({})
const form = reactive<any>({
  invoice_no: '', invoice_date: '', amount: 0, tax_rate: 0, remark: '',
})

function formatMoney(v: number | undefined | null) {
  return (v ?? 0).toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

async function reload(_silent = false) {
  loading.value = true
  try {
    const resp = await erpApi.listInvoices({ direction: direction.value, status: status.value || undefined, limit: 200 })
    items.value = resp?.items ?? []
  } catch (e: any) {
    ElMessage.error(e?.message || t('erp.common.loadFailed'))
  } finally {
    loading.value = false
  }
}

function openCreate() {
  editingId.value = null
  Object.assign(form, { invoice_no: '', invoice_date: '', amount: 0, tax_rate: 0, remark: '' })
  dialogVisible.value = true
}

async function save() {
  saving.value = true
  try {
    await erpApi.createInvoice({
      direction: direction.value, invoice_type: 'special',
      invoice_date: form.invoice_date, amount: form.amount || 0,
      tax_rate: form.tax_rate || 0,
      tax_amount: 0, total_amount: (form.amount || 0) * (1 + (form.tax_rate || 0) / 100),
      invoice_no: form.invoice_no || null, remark: form.remark || null,
      items: [],
    })
    ElMessage.success(t('erp.common.saved'))
    dialogVisible.value = false
    reload(true)
  } catch (e: any) {
    ElMessage.error(e?.message || t('erp.common.saveFailed'))
  } finally {
    saving.value = false
  }
}

async function view(row: InvoiceOut) {
  const d = await erpApi.getInvoice(row.id)
  detail.value = d
  detailVisible.value = true
}

async function post(row: InvoiceOut) {
  await ElMessageBox.confirm(t('erp.common.confirmPost'), '', { type: 'warning' })
  try {
    await erpApi.postInvoice(row.id)
    ElMessage.success(t('erp.common.posted'))
    reload(true)
  } catch (e: any) {
    ElMessage.error(e?.message)
  }
}

async function voidRow(row: InvoiceOut) {
  await ElMessageBox.confirm(t('erp.common.confirmVoid'), '', { type: 'warning' })
  try {
    await erpApi.voidInvoice(row.id)
    ElMessage.success(t('erp.common.voided'))
    reload(true)
  } catch (e: any) {
    ElMessage.error(e?.message)
  }
}

onMounted(() => reload(true))
</script>
