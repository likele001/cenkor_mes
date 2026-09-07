<template>
  <AdminPage :title="t('erp.assets.checks')">
    <template #actions>
      <div class="flex items-center gap-2">
        <el-button type="primary" @click="openCreate">{{ t('erp.common.create') }}</el-button>
        <el-button @click="reload(true)">{{ t('erp.common.refresh') }}</el-button>
      </div>
    </template>

    <div class="mt-4" v-loading="loading">
      <el-table :data="items" border>
        <el-table-column prop="check_no" :label="t('erp.assets.checkNo')" width="140" />
        <el-table-column prop="check_date" :label="t('erp.assets.checkDate')" width="120" />
        <el-table-column prop="status" :label="t('erp.common.status')" width="110">
          <template #default="{ row }"><el-tag size="small">{{ row.status }}</el-tag></template>
        </el-table-column>
        <el-table-column :label="t('erp.common.actions')" width="100" align="center">
          <template #default="{ row }">
            <el-button link type="primary" @click="view(row)">{{ t('erp.common.view') }}</el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-empty v-if="!loading && !items.length" :description="t('erp.common.empty')" />
    </div>

    <el-dialog v-model="dialogVisible" :title="t('erp.assets.createCheck')" width="520px" destroy-on-close>
      <el-form :model="form" label-width="100px">
        <el-form-item :label="t('erp.assets.checkDate')" required>
          <el-date-picker v-model="form.check_date" type="date" value-format="YYYY-MM-DD" style="width:100%" />
        </el-form-item>
        <el-form-item :label="t('erp.common.remark')">
          <el-input v-model="form.remark" type="textarea" :rows="2" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">{{ t('erp.common.cancel') }}</el-button>
        <el-button type="primary" :loading="saving" @click="save">{{ t('erp.common.save') }}</el-button>
      </template>
    </el-dialog>

    <el-drawer v-model="drawerVisible" :title="t('erp.assets.checkDetail')" size="560px">
      <template v-if="detail">
        <el-descriptions :column="2" border size="small">
          <el-descriptions-item :label="t('erp.assets.checkNo')">{{ detail.check_no }}</el-descriptions-item>
          <el-descriptions-item :label="t('erp.common.status')">{{ detail.status }}</el-descriptions-item>
        </el-descriptions>
        <el-table :data="detail.items || []" border class="mt-3" size="small">
          <el-table-column prop="asset_id" :label="t('erp.assets.assetId')" width="80" />
          <el-table-column prop="expected_qty" label="Exp" width="60" />
          <el-table-column prop="checked_qty" label="Chk" width="60" />
          <el-table-column prop="diff_qty" label="Diff" width="60" />
          <el-table-column prop="status" label="Status" width="90" />
        </el-table>
        <el-button v-if="detail.status !== 'done'" type="success" class="mt-3" :loading="completing" @click="complete">
          {{ t('erp.assets.completeCheck') }}
        </el-button>
      </template>
    </el-drawer>
  </AdminPage>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { ElMessage } from 'element-plus'
import AdminPage from '@/components/admin/AdminPage.vue'
import { erpApi, type AssetCheckOut } from '@/api/erp'

const { t } = useI18n()
const loading = ref(false)
const saving = ref(false)
const completing = ref(false)
const items = ref<AssetCheckOut[]>([])
const dialogVisible = ref(false)
const drawerVisible = ref(false)
const detail = ref<AssetCheckOut | null>(null)
const form = reactive<any>({ check_date: '', remark: '' })

async function reload(_silent = false) {
  loading.value = true
  try {
    const resp = await erpApi.listChecks({ limit: 200 })
    items.value = resp?.items ?? []
  } catch (e: any) {
    ElMessage.error(e?.message || t('erp.common.loadFailed'))
  } finally {
    loading.value = false
  }
}

function openCreate() {
  Object.assign(form, { check_date: '', remark: '' })
  dialogVisible.value = true
}

async function save() {
  saving.value = true
  try {
    await erpApi.createCheck({ ...form, items: [] })
    ElMessage.success(t('erp.common.saved'))
    dialogVisible.value = false
    reload(true)
  } catch (e: any) {
    ElMessage.error(e?.message || t('erp.common.saveFailed'))
  } finally {
    saving.value = false
  }
}

async function view(row: AssetCheckOut) {
  detail.value = await erpApi.getCheck(row.id)
  drawerVisible.value = true
}

async function complete() {
  if (!detail.value) return
  completing.value = true
  try {
    await erpApi.completeCheck(detail.value.id)
    ElMessage.success(t('erp.common.saved'))
    drawerVisible.value = false
    reload(true)
  } catch (e: any) {
    ElMessage.error(e?.message)
  } finally {
    completing.value = false
  }
}

onMounted(() => reload(true))
</script>
