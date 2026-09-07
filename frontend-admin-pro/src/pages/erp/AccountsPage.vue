<template>
  <AdminPage :title="t('erp.accounts.title')">
    <template #actions>
      <div class="flex items-center gap-2">
        <el-button type="primary" @click="openCreate">{{ t('erp.common.create') }}</el-button>
        <el-button @click="reload(true)">{{ t('erp.common.refresh') }}</el-button>
      </div>
    </template>

    <div class="mt-4" v-loading="loading">
      <el-table :data="items" border>
        <el-table-column prop="code" :label="t('erp.accounts.code')" width="120" />
        <el-table-column prop="name" :label="t('erp.accounts.name')" min-width="160" />
        <el-table-column :label="t('erp.accounts.type')" width="110">
          <template #default="{ row }"><el-tag size="small">{{ row.subject_type }}</el-tag></template>
        </el-table-column>
        <el-table-column prop="direction" :label="t('erp.accounts.direction')" width="90" />
        <el-table-column prop="opening_balance" :label="t('erp.accounts.openingBalance')" width="120" align="right">
          <template #default="{ row }">¥ {{ formatMoney(row.opening_balance) }}</template>
        </el-table-column>
        <el-table-column :label="t('erp.common.actions')" width="120" align="center">
          <template #default="{ row }">
            <el-button link type="danger" @click="remove(row)">{{ t('erp.common.delete') }}</el-button>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <el-dialog v-model="dialogVisible" :title="t('erp.accounts.create')" width="520px" destroy-on-close>
      <el-form :model="form" label-width="110px">
        <el-form-item :label="t('erp.accounts.code')" required>
          <el-input v-model="form.code" />
        </el-form-item>
        <el-form-item :label="t('erp.accounts.name')" required>
          <el-input v-model="form.name" />
        </el-form-item>
        <el-form-item :label="t('erp.accounts.type')">
          <el-select v-model="form.subject_type" style="width:100%">
            <el-option v-for="tp in ['asset','liability','equity','revenue','cost','expense']" :key="tp" :label="tp" :value="tp" />
          </el-select>
        </el-form-item>
        <el-form-item :label="t('erp.accounts.direction')">
          <el-select v-model="form.direction" style="width:100%">
            <el-option label="debit" value="debit" />
            <el-option label="credit" value="credit" />
          </el-select>
        </el-form-item>
        <el-form-item :label="t('erp.accounts.openingBalance')">
          <el-input-number v-model="form.opening_balance" :precision="2" :controls="false" style="width:100%" />
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
import { erpApi, type AccountOut } from '@/api/erp'

const { t } = useI18n()
const loading = ref(false)
const saving = ref(false)
const items = ref<AccountOut[]>([])
const dialogVisible = ref(false)
const form = reactive<any>({ code: '', name: '', subject_type: 'asset', direction: 'debit', opening_balance: 0 })

function formatMoney(v: number | undefined | null) {
  return (v ?? 0).toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

async function reload(_silent = false) {
  loading.value = true
  try {
    const resp = await erpApi.listAccounts()
    items.value = resp?.items ?? []
  } catch (e: any) {
    ElMessage.error(e?.message || t('erp.common.loadFailed'))
  } finally {
    loading.value = false
  }
}

function openCreate() {
  Object.assign(form, { code: '', name: '', subject_type: 'asset', direction: 'debit', opening_balance: 0 })
  dialogVisible.value = true
}

async function save() {
  saving.value = true
  try {
    await erpApi.createAccount({ ...form })
    ElMessage.success(t('erp.common.saved'))
    dialogVisible.value = false
    reload(true)
  } catch (e: any) {
    ElMessage.error(e?.message || t('erp.common.saveFailed'))
  } finally {
    saving.value = false
  }
}

async function remove(row: AccountOut) {
  await ElMessageBox.confirm(t('erp.common.confirmDelete'), '', { type: 'warning' })
  try {
    await erpApi.deleteAccount(row.id)
    ElMessage.success(t('erp.common.deleted'))
    reload(true)
  } catch (e: any) {
    ElMessage.error(e?.message)
  }
}

onMounted(() => reload(true))
</script>
