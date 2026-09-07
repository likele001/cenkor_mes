<template>
  <AdminPage :title="t('erp.vouchers.title')">
    <template #actions>
      <div class="flex items-center gap-2 flex-wrap">
        <el-date-picker v-model="period" type="month" value-format="YYYY-MM" :placeholder="t('erp.common.period')" @change="reload(true)" />
        <el-button type="primary" @click="openCreate">{{ t('erp.common.create') }}</el-button>
        <el-button @click="reload(true)">{{ t('erp.common.refresh') }}</el-button>
      </div>
    </template>

    <div class="mt-4" v-loading="loading">
      <el-table :data="items" border>
        <el-table-column prop="code" :label="t('erp.vouchers.code')" width="130" />
        <el-table-column prop="voucher_date" :label="t('erp.vouchers.date')" width="110" />
        <el-table-column prop="summary" :label="t('erp.vouchers.summary')" min-width="180" show-overflow-tooltip />
        <el-table-column prop="amount" :label="t('erp.vouchers.amount')" width="120" align="right">
          <template #default="{ row }">¥ {{ formatMoney(row.amount) }}</template>
        </el-table-column>
        <el-table-column prop="status" :label="t('erp.common.status')" width="90">
          <template #default="{ row }">
            <el-tag size="small" :type="row.status === 'posted' ? 'success' : 'info'">{{ row.status }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column :label="t('erp.common.actions')" width="160" align="center" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" @click="view(row)">{{ t('erp.common.view') }}</el-button>
            <el-button v-if="row.status === 'draft'" link type="success" @click="post(row)">{{ t('erp.common.post') }}</el-button>
            <el-button v-if="row.status === 'posted'" link type="warning" @click="unpost(row)">{{ t('erp.common.unpost') }}</el-button>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <el-dialog v-model="dialogVisible" :title="editingId ? t('erp.vouchers.detail') : t('erp.vouchers.create')" width="760px" destroy-on-close>
      <el-form :model="form" label-width="90px">
        <el-form-item :label="t('erp.vouchers.date')">
          <el-date-picker v-model="form.voucher_date" type="date" value-format="YYYY-MM-DD" />
        </el-form-item>
        <el-form-item :label="t('erp.vouchers.summary')">
          <el-input v-model="form.summary" />
        </el-form-item>
        <el-form-item :label="t('erp.vouchers.entries')">
          <div class="w-full space-y-2">
            <div v-for="(e, i) in form.entries" :key="i" class="flex items-center gap-2">
              <el-select v-model="e.account_subject_id" :placeholder="t('erp.accounts.name')" style="width:200px">
                <el-option v-for="a in accountOptions" :key="a.id" :label="a.code + ' ' + a.name" :value="a.id" />
              </el-select>
              <el-input-number v-model="e.debit_amount" :precision="2" :controls="false" :placeholder="t('erp.vouchers.debit')" style="width:140px" />
              <el-input-number v-model="e.credit_amount" :precision="2" :controls="false" :placeholder="t('erp.vouchers.credit')" style="width:140px" />
              <el-button link type="danger" @click="form.entries.splice(i, 1)">✕</el-button>
            </div>
            <div class="text-sm text-gray-500">
              {{ t('erp.vouchers.balanceHint') }}: 借 {{ formatMoney(totalDebit) }} = 贷 {{ formatMoney(totalCredit) }}
              <span v-if="totalDebit !== totalCredit" class="text-red-500 ml-2">{{ t('erp.vouchers.unbalanced') }}</span>
            </div>
            <el-button size="small" @click="form.entries.push({ account_subject_id: undefined, debit_amount: 0, credit_amount: 0 })">
              + {{ t('erp.vouchers.addEntry') }}
            </el-button>
          </div>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">{{ t('erp.common.cancel') }}</el-button>
        <el-button v-if="!editingId" type="primary" :loading="saving" :disabled="totalDebit !== totalCredit || totalDebit <= 0" @click="save">
          {{ t('erp.common.save') }}
        </el-button>
      </template>
    </el-dialog>
  </AdminPage>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { ElMessage, ElMessageBox } from 'element-plus'
import AdminPage from '@/components/admin/AdminPage.vue'
import { erpApi, type VoucherOut } from '@/api/erp'

const { t } = useI18n()
const loading = ref(false)
const saving = ref(false)
const items = ref<VoucherOut[]>([])
const period = ref('')
const accountOptions = ref<Array<{ id: number; code: string; name: string }>>([])
const dialogVisible = ref(false)
const editingId = ref<number | null>(null)
const form = reactive<any>({
  voucher_date: '', summary: '',
  entries: [{ account_subject_id: undefined, debit_amount: 0, credit_amount: 0 }],
})

const totalDebit = computed(() => form.entries.reduce((s: number, e: any) => s + (e.debit_amount || 0), 0))
const totalCredit = computed(() => form.entries.reduce((s: number, e: any) => s + (e.credit_amount || 0), 0))

function formatMoney(v: number | undefined | null) {
  return (v ?? 0).toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

async function reload(_silent = false) {
  loading.value = true
  try {
    const resp = await erpApi.listVouchers({ period: period.value || undefined, limit: 200 })
    items.value = resp?.items ?? []
    accountOptions.value = (await erpApi.accountOptions()) ?? []
  } catch (e: any) {
    ElMessage.error(e?.message || t('erp.common.loadFailed'))
  } finally {
    loading.value = false
  }
}

function openCreate() {
  editingId.value = null
  Object.assign(form, {
    voucher_date: '', summary: '',
    entries: [{ account_subject_id: undefined, debit_amount: 0, credit_amount: 0 }],
  })
  dialogVisible.value = true
}

async function save() {
  saving.value = true
  try {
    await erpApi.createVoucher({
      voucher_date: form.voucher_date, summary: form.summary || null,
      entries: form.entries.map((e: any) => ({ ...e, account_subject_id: Number(e.account_subject_id) })),
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

async function view(row: VoucherOut) {
  editingId.value = row.id
  const d = await erpApi.getVoucher(row.id)
  Object.assign(form, {
    voucher_date: d.voucher_date, summary: d.summary || '',
    entries: (d.entries || []).map((e) => ({ account_subject_id: e.account_subject_id, debit_amount: e.debit_amount, credit_amount: e.credit_amount })),
  })
  dialogVisible.value = true
}

async function post(row: VoucherOut) {
  await ElMessageBox.confirm(t('erp.common.confirmPost'), '', { type: 'warning' })
  try {
    await erpApi.postVoucher(row.id)
    ElMessage.success(t('erp.common.posted'))
    reload(true)
  } catch (e: any) {
    ElMessage.error(e?.message)
  }
}

async function unpost(row: VoucherOut) {
  await ElMessageBox.confirm(t('erp.common.confirmUnpost'), '', { type: 'warning' })
  try {
    await erpApi.unpostVoucher(row.id)
    ElMessage.success(t('erp.common.unposted'))
    reload(true)
  } catch (e: any) {
    ElMessage.error(e?.message)
  }
}

onMounted(() => reload(true))
</script>
