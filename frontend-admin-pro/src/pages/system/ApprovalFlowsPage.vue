<template>
  <AdminPage :title="t('menu.approvalFlows')">
    <el-card class="flex-1 flex flex-col overflow-hidden" body-class="flex-1 overflow-hidden !p-0">
      <template #header>
        <div class="flex items-center justify-between">
          <span class="text-[16px] font-semibold">{{ t('menu.approvalFlows') }}</span>
          <div class="flex items-center gap-2">
            <el-select v-model="filterBiz" clearable placeholder="业务类型" style="width:130px">
              <el-option v-for="(l, k) in BIZ_TYPES" :key="k" :label="l" :value="k" />
            </el-select>
            <el-button type="primary" @click="openCreate">{{ t('production.common.create') }}</el-button>
          </div>
        </div>
      </template>
      <div class="flex-1 overflow-auto p-3 min-h-0">
        <div v-loading="loading">
          <el-table class="hidden lg:block w-full" :data="filtered" stripe border style="width:100%">
            <el-table-column prop="name" label="名称" min-width="150" />
            <el-table-column label="业务类型" width="110">
              <template #default="{row}">{{ BIZ_TYPES[row.biz_type] || row.biz_type }}</template>
            </el-table-column>
            <el-table-column label="审批步骤" min-width="200">
              <template #default="{row}">
                <div class="flex items-center gap-1 flex-wrap">
                  <template v-for="(s, i) in row.steps" :key="s.id">
                    <el-tag size="small" :type="s.is_required ? 'primary' : 'info'">{{ ROLE_LABELS[s.approver_role] || s.approver_role }}</el-tag>
                    <span v-if="i < row.steps.length - 1" class="text-el-placeholder text-xs">→</span>
                  </template>
                  <el-tag v-if="!row.steps.length" size="small" type="warning">无步骤</el-tag>
                </div>
              </template>
            </el-table-column>
            <el-table-column label="状态" width="80">
              <template #default="{row}">
                <el-switch :model-value="row.is_active" @change="toggleActive(row)" />
              </template>
            </el-table-column>
            <el-table-column label="操作" width="220" fixed="right">
              <template #default="{row}">
                <el-button size="small" @click="openSteps(row)">步骤管理</el-button>
                <el-button size="small" @click="openEdit(row)">{{ t('production.common.edit') }}</el-button>
                <el-popconfirm title="确认删除该审批流？" @confirm="doDelete(row)">
                  <template #reference><el-button size="small" type="danger" plain>{{ t('production.common.delete') }}</el-button></template>
                </el-popconfirm>
              </template>
            </el-table-column>
          </el-table>
          <div class="lg:hidden space-y-3">
            <div v-for="row in filtered" :key="row.id" class="admin-mobile-row">
              <div class="admin-mobile-row__head">
                <div class="font-semibold">{{ row.name }}</div>
                <el-switch :model-value="row.is_active" size="small" @change="toggleActive(row)" />
              </div>
              <dl class="admin-mobile-kv">
                <dt>业务</dt><dd>{{ BIZ_TYPES[row.biz_type] || row.biz_type }}</dd>
                <dt>步骤</dt>
                <dd>
                  <div class="flex items-center gap-1 flex-wrap">
                    <el-tag v-for="s in row.steps" :key="s.id" size="small" :type="s.is_required ? 'primary' : 'info'">
                      {{ ROLE_LABELS[s.approver_role] || s.approver_role }}
                    </el-tag>
                    <el-tag v-if="!row.steps.length" size="small" type="warning">无步骤</el-tag>
                  </div>
                </dd>
              </dl>
              <div class="admin-mobile-actions">
                <el-button size="small" @click="openSteps(row)">步骤</el-button>
                <el-button size="small" @click="openEdit(row)">编辑</el-button>
                <el-popconfirm title="确认删除？" @confirm="doDelete(row)">
                  <template #reference><el-button size="small" type="danger" plain>删除</el-button></template>
                </el-popconfirm>
              </div>
            </div>
            <el-empty v-if="!loading && !filtered.length" description="暂无审批流" />
          </div>
        </div>
      </div>
    </el-card>

    <!-- 新建/编辑 -->
    <el-dialog v-model="dlg.open" :title="dlg.isEdit ? '编辑审批流' : '新建审批流'" width="480px" destroy-on-close>
      <el-form ref="formRef" :model="dlg.form" :rules="rules" label-width="80px">
        <el-form-item label="名称" prop="name">
          <el-input v-model="dlg.form.name" placeholder="如：生产报工审批" />
        </el-form-item>
        <el-form-item label="业务类型" prop="biz_type">
          <el-select v-model="dlg.form.biz_type" :disabled="dlg.isEdit" style="width:100%">
            <el-option v-for="(l, k) in BIZ_TYPES" :key="k" :label="l" :value="k" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dlg.open = false">{{ t('production.common.cancel') }}</el-button>
        <el-button type="primary" :loading="dlg.saving" @click="save">{{ t('production.common.save') }}</el-button>
      </template>
    </el-dialog>

    <!-- 步骤管理弹窗 -->
    <el-dialog v-model="stepDlg.open" :title="`步骤管理：${stepDlg.flow?.name || ''}`" width="600px" destroy-on-close>
      <div v-loading="stepDlg.loading" class="space-y-3">
        <div v-for="(s, i) in stepDlg.steps" :key="i" class="flex items-center gap-2 p-2 border rounded">
          <el-tag size="small">{{ i + 1 }}</el-tag>
          <el-select v-model="s.approver_role" style="width:120px">
            <el-option v-for="(l, k) in ROLE_LABELS" :key="k" :label="l" :value="k" />
          </el-select>
          <el-input v-model="s.label" placeholder="步骤标签" style="width:140px" />
          <el-checkbox v-model="s.is_required">必审</el-checkbox>
          <el-checkbox v-model="s.can_skip">可跳过</el-checkbox>
          <el-button size="small" type="danger" :disabled="stepDlg.steps.length <= 1" @click="stepDlg.steps.splice(i, 1)">删除</el-button>
        </div>
        <el-button size="small" @click="stepDlg.steps.push({ approver_role: 'leader', is_required: true, can_skip: false, label: '' })">+ 添加步骤</el-button>
      </div>
      <template #footer>
        <el-button @click="stepDlg.open = false">{{ t('production.common.cancel') }}</el-button>
        <el-button type="primary" :loading="stepDlg.saving" @click="saveSteps">{{ t('production.common.save') }}</el-button>
      </template>
    </el-dialog>
  </AdminPage>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { ElMessage } from 'element-plus'
import AdminPage from '@/components/admin/AdminPage.vue'
import { approvalApi, type ApprovalFlowOut, type ApprovalStep, BIZ_TYPES, ROLE_LABELS } from '@/api/approval'

const { t } = useI18n()

const loading = ref(false)
const items = ref<ApprovalFlowOut[]>([])
const filterBiz = ref('')

const filtered = computed(() => {
  if (!filterBiz.value) return items.value
  return items.value.filter(f => f.biz_type === filterBiz.value)
})

function fetchList() {
  loading.value = true
  approvalApi.list(filterBiz.value || undefined).then(r => { items.value = r.items }).finally(() => { loading.value = false })
}

// CRUD
const formRef = ref()
const dlg = reactive({
  open: false, isEdit: false, saving: false,
  form: {} as Record<string, any>,
})
const rules = { name: [{ required: true, message: '请输入名称' }], biz_type: [{ required: true, message: '请选择业务类型' }] }

function resetForm() { dlg.form = { name: '', biz_type: 'report', is_active: true } }
function openCreate() { resetForm(); dlg.isEdit = false; dlg.open = true }
function openEdit(row: ApprovalFlowOut) {
  dlg.form = { name: row.name, biz_type: row.biz_type }
  dlg.isEdit = true; dlg.open = true
}
function save() {
  formRef.value?.validate((valid: boolean) => {
    if (!valid) return
    dlg.saving = true
    const data = { name: dlg.form.name, biz_type: dlg.form.biz_type }
    const action = dlg.isEdit
      ? approvalApi.update((items.value.find(f => f.name === dlg.form.name)?.id)!, { name: dlg.form.name })
      : approvalApi.create(data)
    action.then(() => {
      ElMessage.success(dlg.isEdit ? '已更新' : '已创建')
      dlg.open = false; fetchList()
    }).finally(() => { dlg.saving = false })
  })
}
function doDelete(row: ApprovalFlowOut) {
  approvalApi.delete(row.id).then(() => { ElMessage.success('已删除'); fetchList() })
}
function toggleActive(row: ApprovalFlowOut) {
  approvalApi.update(row.id, { is_active: !row.is_active }).then(r => {
    row.is_active = r.is_active
    ElMessage.success(r.is_active ? '已启用' : '已停用')
  }).catch(() => {})
}

// Steps
const stepDlg = reactive({
  open: false, loading: false, saving: false,
  flow: null as ApprovalFlowOut | null,
  steps: [] as { approver_role: string; is_required: boolean; can_skip: boolean; label: string }[],
})
function openSteps(row: ApprovalFlowOut) {
  stepDlg.flow = row; stepDlg.open = true; stepDlg.loading = true
  stepDlg.steps = row.steps.length
    ? row.steps.map(s => ({ approver_role: s.approver_role, is_required: s.is_required, can_skip: s.can_skip, label: s.label || '' }))
    : [{ approver_role: 'leader', is_required: true, can_skip: false, label: '' }]
  stepDlg.loading = false
}
function saveSteps() {
  if (!stepDlg.flow) return
  if (!stepDlg.steps.length) { ElMessage.warning('至少需要一个步骤'); return }
  stepDlg.saving = true
  approvalApi.setSteps(stepDlg.flow.id, stepDlg.steps.map((s, i) => ({ ...s, step_order: i + 1 }))).then(() => {
    ElMessage.success('步骤已更新'); stepDlg.open = false; fetchList()
  }).finally(() => { stepDlg.saving = false })
}

onMounted(fetchList)
</script>
