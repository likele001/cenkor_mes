<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { ElMessage } from 'element-plus'
import AdminPage from '@/components/admin/AdminPage.vue'
import { http } from '@/utils/http'

interface TemplateItem {
  id?: number
  seq: number
  item_name: string
  item_type: string
  standard_value: string | null
  upper_limit: string | null
  lower_limit: string | null
  unit: string | null
  is_required: boolean
  remark: string | null
}

interface Template {
  id: number
  code: string
  name: string
  description: string | null
  process_id: number | null
  product_id: number | null
  is_active: boolean
  items: TemplateItem[]
}

const { t } = useI18n()
const loading = ref(false)
const industryFilter = ref('')
const activeIndustries = ref<{code:string,name:string}[]>([])
const items = ref<Template[]>([])
const dialogVisible = ref(false)
const editing = ref(false)
const form = ref<{
  code: string
  name: string
  description: string
  process_id: number | null
  product_id: number | null
  items: TemplateItem[]
}>({
  code: '',
  name: '',
  description: '',
  process_id: null,
  product_id: null,
  items: [],
})
const editId = ref<number | null>(null)
const saving = ref(false)

async function load() {
  loading.value = true
  try {
    const data = await http.get<{ items: Template[] }>('/admin/production/inspection-templates')
    items.value = (data.items || []) as Template[]
  } catch { items.value = [] } finally { loading.value = false }
}

function resetForm() {
  form.value = { code: '', name: '', description: '', process_id: null, product_id: null, items: [] }
  editId.value = null
  editing.value = false
}

function openCreate() {
  resetForm()
  dialogVisible.value = true
}

function openEdit(row: Template) {
  form.value = {
    code: row.code,
    name: row.name,
    description: row.description || '',
    process_id: row.process_id,
    product_id: row.product_id,
    items: (row.items || []).map((it, i) => ({ ...it, seq: i + 1 })),
  }
  editId.value = row.id
  editing.value = true
  dialogVisible.value = true
}

function addItem() {
  form.value.items.push({
    seq: form.value.items.length + 1,
    item_name: '',
    item_type: 'pass_fail',
    standard_value: null,
    upper_limit: null,
    lower_limit: null,
    unit: null,
    is_required: true,
    remark: null,
  })
}

function removeItem(idx: number) {
  form.value.items.splice(idx, 1)
  form.value.items.forEach((it, i) => { it.seq = i + 1 })
}

async function save() {
  if (!form.value.code.trim()) { ElMessage.warning(t('production.inspectionTemplates.pleaseInputCode')); return }
  if (!form.value.name.trim()) { ElMessage.warning(t('production.inspectionTemplates.pleaseInputName')); return }
  saving.value = true
  try {
    const payload = {
      ...form.value,
      items: form.value.items.map(({ id, ...rest }) => rest),
    }
    if (editId.value) {
      await http.put(`/admin/production/inspection-templates/${editId.value}`, payload)
    } else {
      await http.post('/admin/production/inspection-templates', payload)
    }
    ElMessage.success(t('production.inspectionTemplates.saveSuccess'))
    dialogVisible.value = false
    await load()
  } catch { ElMessage.error(t('production.inspectionTemplates.saveFailed')) } finally { saving.value = false }
}

async function deleteRow(row: Template) {
  try {
    await http.delete(`/admin/production/inspection-templates/${row.id}`)
    ElMessage.success(t('production.inspectionTemplates.disabledSuccess'))
    await load()
  } catch { ElMessage.error(t('production.inspectionTemplates.operationFailed')) }
}

onMounted(load)
</script>

<template>
  <AdminPage :title="t('production.inspectionTemplates.title')">
    <template #actions>
      <el-button type="primary" @click="openCreate">{{ t('production.inspectionTemplates.addTemplate') }}</el-button>
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
    <el-table-column prop="code" label="编码" width="140" />
        <div style="margin-bottom:15px">
      <el-select v-model="industryFilter" placeholder="全部行业" clearable style="width:140px" @change="load">
        <el-option label="全部行业" value="" />
        <el-option v-for="ind in activeIndustries" :key="ind.code" :label="ind.name" :value="ind.code" />
      </el-select>
    </div>
    <el-table-column prop="name" label="名称" min-width="180" />
        <div style="margin-bottom:15px">
      <el-select v-model="industryFilter" placeholder="全部行业" clearable style="width:140px" @change="load">
        <el-option label="全部行业" value="" />
        <el-option v-for="ind in activeIndustries" :key="ind.code" :label="ind.name" :value="ind.code" />
      </el-select>
    </div>
    <el-table-column prop="description" label="描述" min-width="200">
          <template #default="{ row }">{{ row.description || '—' }}</template>
        </el-table-column>
        <div style="margin-bottom:15px">
      <el-select v-model="industryFilter" placeholder="全部行业" clearable style="width:140px" @change="load">
        <el-option label="全部行业" value="" />
        <el-option v-for="ind in activeIndustries" :key="ind.code" :label="ind.name" :value="ind.code" />
      </el-select>
    </div>
    <el-table-column label="关联工序" width="120">
          <template #default="{ row }">{{ row.process_id ? `#${row.process_id}` : '全局' }}</template>
        </el-table-column>
        <div style="margin-bottom:15px">
      <el-select v-model="industryFilter" placeholder="全部行业" clearable style="width:140px" @change="load">
        <el-option label="全部行业" value="" />
        <el-option v-for="ind in activeIndustries" :key="ind.code" :label="ind.name" :value="ind.code" />
      </el-select>
    </div>
    <el-table-column label="检查项数" width="100">
          <template #default="{ row }">{{ row.items?.length || 0 }}</template>
        </el-table-column>
        <div style="margin-bottom:15px">
      <el-select v-model="industryFilter" placeholder="全部行业" clearable style="width:140px" @change="load">
        <el-option label="全部行业" value="" />
        <el-option v-for="ind in activeIndustries" :key="ind.code" :label="ind.name" :value="ind.code" />
      </el-select>
    </div>
    <el-table-column label="操作" width="180" fixed="right">
          <template #default="{ row }">
            <el-button size="small" @click="openEdit(row)">{{ t('production.inspectionTemplates.edit') }}</el-button>
            <el-popconfirm title="确认停用？" @confirm="deleteRow(row)">
              <template #reference>
                <el-button size="small" type="danger" :disabled="!row.is_active">{{ t('production.inspectionTemplates.disableBtn') }}</el-button>
              </template>
            </el-popconfirm>
          </template>
        </el-table-column>
      </el-table>

      <div class="lg:hidden space-y-3">
        <div v-for="row in items" :key="row.id" class="admin-mobile-row">
          <div class="admin-mobile-row__head">
            <div class="font-semibold">{{ row.name }}</div>
            <el-tag size="small">{{ row.code }}</el-tag>
          </div>
          <dl class="admin-mobile-kv">
            <dt>检查项</dt>
            <dd>{{ row.items?.length || 0 }} 项</dd>
          </dl>
          <div class="admin-mobile-actions">
            <el-button size="small" @click="openEdit(row)">{{ t('production.inspectionTemplates.edit') }}</el-button>
            <el-popconfirm title="确认停用？" @confirm="deleteRow(row)">
              <template #reference><el-button size="small" type="danger">{{ t('production.inspectionTemplates.disableBtn') }}</el-button></template>
            </el-popconfirm>
          </div>
        </div>
        <el-empty v-if="!loading && !items.length" description="暂无质检模板" />
      </div>
    </div>

    <el-dialog v-model="dialogVisible" :title="editing ? t('production.inspectionTemplates.editTitle') : t('production.inspectionTemplates.createTitle')" width="800px" top="5vh">
      <el-form :model="form" label-width="100px">
        <el-row :gutter="16">
          <el-col :span="8">
            <el-form-item label="编码" required>
              <el-input v-model="form.code" placeholder="如 QC-WELD-001" :disabled="editing" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="名称" required>
              <el-input v-model="form.name" placeholder="如 焊接工序检查项" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="工序ID">
              <el-input-number v-model="form.process_id" :min="0" :max="99999" placeholder="0=全局" style="width:100%" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="描述">
          <el-input v-model="form.description" type="textarea" :rows="2" />
        </el-form-item>

        <el-divider>{{ t('production.inspectionTemplates.inspectionItems') }}</el-divider>
        <div v-for="(it, idx) in form.items" :key="idx" class="border rounded p-3 mb-2">
          <div class="flex items-center gap-2 mb-2">
            <span class="text-sm font-medium text-zinc-600">#{{ it.seq }}</span>
            <el-button size="small" type="danger" text @click="removeItem(idx)">{{ t('production.inspectionTemplates.delete') }}</el-button>
          </div>
          <el-row :gutter="8">
            <el-col :span="8">
              <el-input v-model="it.item_name" placeholder="检查项名称" size="small" />
            </el-col>
            <el-col :span="5">
              <el-select v-model="it.item_type" size="small" style="width:100%">
                <el-option label="合格/不合格" value="pass_fail" />
                <el-option label="测量值" value="measure" />
                <el-option label="文本描述" value="text" />
              </el-select>
            </el-col>
            <el-col :span="3">
              <el-input v-model="it.standard_value" placeholder="标准值" size="small" />
            </el-col>
            <el-col :span="3">
              <el-input v-model="it.upper_limit" placeholder="上限" size="small" />
            </el-col>
            <el-col :span="3">
              <el-input v-model="it.lower_limit" placeholder="下限" size="small" />
            </el-col>
            <el-col :span="2">
              <el-switch v-model="it.is_required" size="small" active-text="必填" />
            </el-col>
          </el-row>
        </div>
        <el-button size="small" @click="addItem">+ 添加检查项</el-button>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">{{ t('production.common.cancel') }}</el-button>
        <el-button type="primary" :loading="saving" @click="save">{{ t('production.common.save') }}</el-button>
      </template>
    </el-dialog>
  </AdminPage>
</template>
