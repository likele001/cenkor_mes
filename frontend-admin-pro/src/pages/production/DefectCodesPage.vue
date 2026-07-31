<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { ElMessage } from 'element-plus'
import AdminPage from '@/components/admin/AdminPage.vue'
import { http } from '@/utils/http'

interface DefectCode {
  id: number
  code: string
  name: string
  severity: string
  description: string | null
  is_active: boolean
}

const { t } = useI18n()
const loading = ref(false)
const industryFilter = ref('')
const activeIndustries = ref<{code:string,name:string}[]>([])
const exporting = ref(false)
const items = ref<DefectCode[]>([])
const dialogVisible = ref(false)
const editing = ref(false)
const form = ref({ code: '', name: '', severity: 'minor', description: '' })
const editId = ref<number | null>(null)
const saving = ref(false)

async function exportExcel() {
  if (exporting.value) return
  exporting.value = true
  try {
    const blob = await http.downloadBlob({ url: '/admin/production/quality/defect-codes/export', method: 'GET' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `defect_codes_${new Date().toISOString().slice(0, 10)}.xlsx`
    a.click()
    URL.revokeObjectURL(url)
    ElMessage.success('导出成功')
  } catch { /* http 已提示 */
  } finally { exporting.value = false }
}

async function load() {
  loading.value = true
  try {
    const data = await http.get<{ items: DefectCode[] }>('/admin/production/defect-codes')
    items.value = (data.items || []) as DefectCode[]
  } catch { items.value = [] } finally { loading.value = false }
}

function resetForm() {
  form.value = { code: '', name: '', severity: 'minor', description: '' }
  editId.value = null
  editing.value = false
}

function openCreate() {
  resetForm()
  dialogVisible.value = true
}

function openEdit(row: DefectCode) {
  form.value = {
    code: row.code,
    name: row.name,
    severity: row.severity,
    description: row.description || '',
  }
  editId.value = row.id
  editing.value = true
  dialogVisible.value = true
}

async function save() {
  if (!form.value.code.trim()) { ElMessage.warning(t('production.defectCodes.pleaseInputCode')); return }
  if (!form.value.name.trim()) { ElMessage.warning(t('production.defectCodes.pleaseInputName')); return }
  saving.value = true
  try {
    if (editId.value) {
      await http.put(`/admin/production/defect-codes/${editId.value}`, form.value)
    } else {
      await http.post('/admin/production/defect-codes', form.value)
    }
    ElMessage.success(t('production.defectCodes.saveSuccess'))
    dialogVisible.value = false
    await load()
  } catch { ElMessage.error(t('production.defectCodes.saveFailed')) } finally { saving.value = false }
}

async function deleteRow(row: DefectCode) {
  try {
    await http.delete(`/admin/production/defect-codes/${row.id}`)
    ElMessage.success(t('production.defectCodes.deletedSuccess'))
    await load()
  } catch { ElMessage.error(t('production.defectCodes.operationFailed')) }
}

function severityLabel(s: string) {
  const m: Record<string, string> = { critical: t('production.defectCodes.critical'), major: t('production.defectCodes.major'), minor: t('production.defectCodes.minor') }
  return m[s] || s
}

function severityType(s: string): 'danger' | 'warning' | 'info' {
  if (s === 'critical') return 'danger'
  if (s === 'major') return 'warning'
  return 'info'
}

onMounted(load)
</script>

<template>
  <AdminPage :title="t('production.defectCodes.title')">
    <template #actions>
      <el-button :loading="exporting" @click="exportExcel">{{ t('common.exportExcel') }}</el-button>
      <el-button type="primary" @click="openCreate">{{ t('production.defectCodes.addDefect') }}</el-button>
    </template>

    <div class="mt-4" v-loading="loading">
      <div style="margin-bottom:15px">
      <el-select v-model="industryFilter" placeholder="全部行业" clearable style="width:140px" @change="load">
        <el-option label="全部行业" value="" />
        <el-option v-for="ind in activeIndustries" :key="ind.code" :label="ind.name" :value="ind.code" />
      </el-select>
    </div>
    <el-table class="hidden lg:block w-full" :data="items" border>
        <div style="margin-bottom:15px">
      <el-select v-model="industryFilter" placeholder="全部行业" clearable style="width:140px" @change="load">
        <el-option label="全部行业" value="" />
        <el-option v-for="ind in activeIndustries" :key="ind.code" :label="ind.name" :value="ind.code" />
      </el-select>
    </div>
    <el-table-column prop="id" label="ID" width="70" />
        <div style="margin-bottom:15px">
      <el-select v-model="industryFilter" placeholder="全部行业" clearable style="width:140px" @change="load">
        <el-option label="全部行业" value="" />
        <el-option v-for="ind in activeIndustries" :key="ind.code" :label="ind.name" :value="ind.code" />
      </el-select>
    </div>
    <el-table-column prop="code" :label="t('production.defectCodes.code')" width="140" />
        <div style="margin-bottom:15px">
      <el-select v-model="industryFilter" placeholder="全部行业" clearable style="width:140px" @change="load">
        <el-option label="全部行业" value="" />
        <el-option v-for="ind in activeIndustries" :key="ind.code" :label="ind.name" :value="ind.code" />
      </el-select>
    </div>
    <el-table-column prop="name" :label="t('production.defectCodes.name')" min-width="180" />
        <div style="margin-bottom:15px">
      <el-select v-model="industryFilter" placeholder="全部行业" clearable style="width:140px" @change="load">
        <el-option label="全部行业" value="" />
        <el-option v-for="ind in activeIndustries" :key="ind.code" :label="ind.name" :value="ind.code" />
      </el-select>
    </div>
    <el-table-column label="严重程度" width="120">
          <template #default="{ row }">
            <el-tag :type="severityType(row.severity)">{{ severityLabel(row.severity) }}</el-tag>
          </template>
        </el-table-column>
        <div style="margin-bottom:15px">
      <el-select v-model="industryFilter" placeholder="全部行业" clearable style="width:140px" @change="load">
        <el-option label="全部行业" value="" />
        <el-option v-for="ind in activeIndustries" :key="ind.code" :label="ind.name" :value="ind.code" />
      </el-select>
    </div>
    <el-table-column prop="description" :label="t('production.defectCodes.description')" min-width="200">
          <template #default="{ row }">{{ row.description || '—' }}</template>
        </el-table-column>
        <div style="margin-bottom:15px">
      <el-select v-model="industryFilter" placeholder="全部行业" clearable style="width:140px" @change="load">
        <el-option label="全部行业" value="" />
        <el-option v-for="ind in activeIndustries" :key="ind.code" :label="ind.name" :value="ind.code" />
      </el-select>
    </div>
    <el-table-column label="操作" width="180" fixed="right">
          <template #default="{ row }">
            <el-button size="small" @click="openEdit(row)">{{ t('production.defectCodes.edit') }}</el-button>
            <el-popconfirm title="确认删除？" @confirm="deleteRow(row)">
              <template #reference>
                <el-button size="small" type="danger">{{ t('production.defectCodes.deleteBtn') }}</el-button>
              </template>
            </el-popconfirm>
          </template>
        </el-table-column>
      </el-table>

      <div class="lg:hidden space-y-3">
        <div v-for="row in items" :key="row.id" class="admin-mobile-row">
          <div class="admin-mobile-row__head">
            <div class="font-semibold">{{ row.name }}</div>
            <el-tag :type="severityType(row.severity)" size="small">{{ severityLabel(row.severity) }}</el-tag>
          </div>
          <dl class="admin-mobile-kv">
            <dt>编码</dt>
            <dd>{{ row.code }}</dd>
          </dl>
          <div class="admin-mobile-actions">
            <el-button size="small" @click="openEdit(row)">{{ t('production.defectCodes.edit') }}</el-button>
            <el-popconfirm title="确认删除？" @confirm="deleteRow(row)">
              <template #reference><el-button size="small" type="danger">{{ t('production.defectCodes.deleteBtn') }}</el-button></template>
            </el-popconfirm>
          </div>
        </div>
        <el-empty v-if="!loading && !items.length" description="暂无缺陷代码" />
      </div>
    </div>

    <el-dialog v-model="dialogVisible" :title="editing ? t('production.defectCodes.editTitle') : t('production.defectCodes.createTitle')" width="500px">
      <el-form :model="form" label-width="100px">
        <el-form-item :label="t('production.defectCodes.code')" required>
          <el-input v-model="form.code" placeholder="如 SCR-001" :disabled="editing" />
        </el-form-item>
        <el-form-item :label="t('production.defectCodes.name')" required>
          <el-input v-model="form.name" placeholder="如 表面划伤" />
        </el-form-item>
        <el-form-item label="严重程度">
          <el-select v-model="form.severity" style="width:100%">
            <el-option label="致命 (Critical)" value="critical" />
            <el-option label="主要 (Major)" value="major" />
            <el-option label="次要 (Minor)" value="minor" />
          </el-select>
        </el-form-item>
        <el-form-item :label="t('production.defectCodes.description')">
          <el-input v-model="form.description" type="textarea" :rows="3" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">{{ t('production.common.cancel') }}</el-button>
        <el-button type="primary" :loading="saving" @click="save">{{ t('production.common.save') }}</el-button>
      </template>
    </el-dialog>
  </AdminPage>
</template>
