<template>
  <AdminPage :title="t('system.printTemplates.title')">
    <template #actions>
      <div class="flex items-center gap-2 flex-wrap">
          <el-input v-model="query.keyword" :placeholder="t('system.printTemplates.searchPlaceholder')" style="width: 220px" @keyup.enter="reload(true)" />
          <el-select v-model="query.template_type" clearable :placeholder="t('system.printTemplates.typePlaceholder')" style="width: 140px" @change="reload(true)">
            <el-option label="HTML" value="html" />
          </el-select>
          <el-checkbox v-model="query.include_inactive" @change="reload(true)">{{ t('system.printTemplates.includeDisabled') }}</el-checkbox>
          <el-button type="primary" @click="openCreate">{{ t('system.printTemplates.create') }}</el-button>
          <el-button @click="reload(true)">{{ t('system.printTemplates.refresh') }}</el-button>
        </div>
    </template>

    <div class="mt-4" v-loading="loading">
        <el-table class="hidden lg:block w-full" :data="items" border>
          <el-table-column prop="id" label="ID" width="90" />
          <el-table-column prop="code" :label="t('system.printTemplates.code')" width="220" />
          <el-table-column prop="name" :label="t('system.printTemplates.name')" min-width="220" />
          <el-table-column prop="template_type" :label="t('system.printTemplates.templateType')" width="120" />
          <el-table-column :label="t('system.printTemplates.status')" width="100">
            <template #default="{ row }">
              <el-tag :type="row.is_active ? 'success' : 'info'">{{ row.is_active ? t('system.printTemplates.enabled') : t('system.printTemplates.disabled') }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="updated_at" :label="t('system.printTemplates.updateTime')" width="180" />
          <el-table-column :label="t('system.printTemplates.operation')" width="260" fixed="right">
            <template #default="{ row }">
              <el-button size="small" @click="openPreview(row)">{{ t('system.printTemplates.preview') }}</el-button>
              <el-button size="small" @click="openEdit(row)">{{ t('system.printTemplates.edit') }}</el-button>
              <el-popconfirm :title="t('system.printTemplates.confirmDisable')" @confirm="onDisable(row)">
                <template #reference>
                  <el-button size="small" type="danger" :disabled="!row.is_active">{{ t('system.printTemplates.disable') }}</el-button>
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
                <div class="text-xs text-el-placeholder">{{ row.code }} · {{ row.template_type }}</div>
              </div>
              <el-tag :type="row.is_active ? 'success' : 'info'" size="small">{{ row.is_active ? t('system.printTemplates.enabled') : t('system.printTemplates.disabled') }}</el-tag>
            </div>
            <dl class="admin-mobile-kv">
              <dt>{{ t('system.printTemplates.update') }}</dt>
              <dd>{{ row.updated_at || '—' }}</dd>
            </dl>
            <div class="admin-mobile-actions">
              <el-button size="small" @click="openPreview(row)">{{ t('system.printTemplates.preview') }}</el-button>
              <el-button size="small" @click="openEdit(row)">{{ t('system.printTemplates.edit') }}</el-button>
              <el-popconfirm :title="t('system.printTemplates.confirmDisable')" @confirm="onDisable(row)">
                <template #reference>
                  <el-button size="small" type="danger" :disabled="!row.is_active">{{ t('system.printTemplates.disable') }}</el-button>
                </template>
              </el-popconfirm>
            </div>
          </div>
          <el-empty v-if="!loading && !items.length" :description="t('system.printTemplates.noTemplates')" />
        </div>
      </div>

      <div class="mt-4 flex justify-end">
        <el-pagination
          background
          layout="prev, pager, next"
          :total="pager.total"
          :page-size="query.limit"
          :current-page="pager.page"
          @current-change="onPage"
        />
      </div>

    <template #extra>
      <el-dialog v-model="dlg.open" :title="dlg.id ? t('system.printTemplates.editTemplate') : t('system.printTemplates.createTemplate')" width="860px" destroy-on-close>
            <el-form ref="formRef" :model="dlg.form" :rules="rules" label-width="90px">
              <el-row :gutter="12">
                <el-col :span="10">
                  <el-form-item :label="t('system.printTemplates.code')" prop="code">
                    <el-input v-model="dlg.form.code" :placeholder="t('system.printTemplates.codePlaceholder')" />
                  </el-form-item>
                </el-col>
                <el-col :span="14">
                  <el-form-item :label="t('system.printTemplates.name')" prop="name">
                    <el-input v-model="dlg.form.name" />
                  </el-form-item>
                </el-col>
              </el-row>

              <el-row :gutter="12">
                <el-col :span="10">
                  <el-form-item :label="t('system.printTemplates.templateType')" prop="template_type">
                    <el-select v-model="dlg.form.template_type" style="width: 100%">
                      <el-option label="HTML" value="html" />
                    </el-select>
                  </el-form-item>
                </el-col>
                <el-col :span="14">
                  <el-form-item :label="t('system.printTemplates.status')" prop="is_active">
                    <el-switch v-model="dlg.form.is_active" :active-text="t('system.printTemplates.enabled')" :inactive-text="t('system.printTemplates.disabled')" />
                  </el-form-item>
                </el-col>
              </el-row>

              <el-form-item :label="t('system.printTemplates.content')" prop="content">
                <el-input v-model="dlg.form.content" type="textarea" :rows="14" :placeholder="t('system.printTemplates.contentPlaceholder')" />
              </el-form-item>

              <el-alert
                v-if="activeGuide"
                :title="`${t('system.printTemplates.variableHint')}：${activeGuide.title}`"
                type="info"
                show-icon
                :closable="false"
              >
                <div class="flex flex-wrap gap-2">
                  <el-tag v-for="v in activeGuide.variables" :key="v" size="small">{{ v }}</el-tag>
                </div>
                <div class="text-xs text-zinc-500 mt-2" v-html="t('system.printTemplates.variableHintDesc')">
                </div>
              </el-alert>
            </el-form>
            <template #footer>
              <el-button @click="dlg.open = false">{{ t('system.printTemplates.cancel') }}</el-button>
              <el-button type="primary" :loading="dlg.saving" @click="onSave">{{ t('system.printTemplates.save') }}</el-button>
            </template>
          </el-dialog>

      <el-dialog v-model="preview.open" :title="t('system.printTemplates.templatePreview')" width="980px" destroy-on-close>
            <el-row :gutter="12">
              <el-col :span="10">
                <el-card shadow="never">
                  <template #header>{{ t('system.printTemplates.sampleData') }}</template>
                  <el-input v-model="preview.dataText" type="textarea" :rows="18" />
                  <div class="mt-3 flex items-center gap-2">
                    <el-button type="primary" :loading="preview.loading" @click="doRender">{{ t('system.printTemplates.render') }}</el-button>
                    <el-button v-if="previewGuide" @click="applyPreviewSample">{{ t('system.printTemplates.loadSample') }}</el-button>
                    <el-button :disabled="!preview.id" :loading="preview.exporting" @click="exportPdf">{{ t('system.printTemplates.exportPdf') }}</el-button>
                    <el-button :disabled="!preview.html" @click="openPrintWindow">{{ t('system.printTemplates.openPrintWindow') }}</el-button>
                  </div>
                  <div v-if="previewGuide" class="mt-3">
                    <div class="text-sm font-medium">{{ t('system.printTemplates.availablePlaceholders') }}</div>
                    <div class="mt-2 flex flex-wrap gap-2">
                      <el-tag v-for="v in previewGuide.variables" :key="v" size="small" type="info">{{ v }}</el-tag>
                    </div>
                  </div>
                </el-card>
              </el-col>
              <el-col :span="14">
                <el-card shadow="never">
                  <template #header>{{ t('system.printTemplates.renderResult') }}</template>
                  <div class="border rounded p-3 bg-white min-h-[420px] overflow-auto" v-html="preview.html"></div>
                </el-card>
              </el-col>
            </el-row>
          </el-dialog>
    </template>
  </AdminPage>
</template>

<script setup lang="ts">
import AdminPage from '@/components/admin/AdminPage.vue'
import { onMounted, reactive, ref, watch } from 'vue'
import type { FormInstance, FormRules } from 'element-plus'
import { ElMessage } from 'element-plus'
import { useI18n } from 'vue-i18n'
import { systemApi, type PrintTemplateOut } from '@/api/system'
import { http } from '@/utils/http'
import { openPrintWindow as openPrintHtmlWindow } from '@/utils/print'

const { t } = useI18n()

const loading = ref(false)
const items = ref<PrintTemplateOut[]>([])
const pager = reactive({ total: 0, page: 1 })
const query = reactive({
  keyword: '',
  template_type: '' as '' | 'html',
  include_inactive: false,
  offset: 0,
  limit: 20,
})

const dlg = reactive({
  open: false,
  saving: false,
  id: 0 as number | 0,
  form: { code: '', name: '', template_type: 'html', content: '', is_active: true },
})

const preview = reactive({
  open: false,
  id: 0 as number | 0,
  code: '',
  loading: false,
  exporting: false,
  dataText: '{\n  \"order\": {\"code\": \"ORD001\"},\n  \"user\": {\"full_name\": \"张三\"},\n  \"task\": {\"task_code\": \"T001\"}\n}\n',
  html: '',
})

type TemplateGuide = {
  title: string
  variables: string[]
  sample: any
}

const TEMPLATE_GUIDES: Record<string, TemplateGuide> = {
  task_label: {
    title: '任务码标签（二维码）',
    variables: [
      'task.task_code',
      'task.seq',
      'task.planned_qty',
      'task.status',
      'process.code',
      'process.name',
      'sku.code',
      'sku.name',
      'work_order.id',
      'work_order.order_id',
      'work_order.qty',
      'qr.text',
      'qr.svg',
    ],
    sample: {
      task: { id: 1, task_code: 'T001', seq: 1, planned_qty: 100, status: 'pending' },
      process: { id: 1, code: 'P001', name: '焊接' },
      sku: { id: 1, code: 'SKU001', name: '示例型号' },
      work_order: { id: 10, order_id: 1001, qty: 1000 },
      qr: { text: 'T001', svg: '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10"><rect width="10" height="10" fill="#000"/></svg>' },
    },
  },
  customer_statement: {
    title: '客户对账单（明细打印）',
    variables: [
      'statement.code',
      'statement.period_start',
      'statement.period_end',
      'statement.total_amount',
      'statement.status',
      'statement.remark',
      'customer.code',
      'customer.name',
      'items_html',
      'printed_at',
    ],
    sample: {
      statement: { id: 1, code: 'STMT001', period_start: '2026-05-01', period_end: '2026-05-15', total_amount: '1234.50', status: 'draft', remark: '' },
      customer: { id: 1, code: 'C001', name: '示例客户' },
      items_html:
        '<tr><td style="padding:6px;border:1px solid #ddd;">100</td><td style="padding:6px;border:1px solid #ddd;">ORD001</td><td style="padding:6px;border:1px solid #ddd;text-align:right;">1234.50</td></tr>',
      printed_at: '2026-05-17 10:00:00',
    },
  },
  supplier_statement: {
    title: '采购对账单（明细打印）',
    variables: [
      'statement.code',
      'statement.period_from',
      'statement.period_to',
      'statement.amount',
      'statement.status',
      'supplier.code',
      'supplier.name',
      'items_html',
      'printed_at',
    ],
    sample: {
      statement: { id: 1, code: 'SSTMT001', period_from: '2026-05-01', period_to: '2026-05-15', amount: '888.00', status: 'draft' },
      supplier: { id: 1, code: 'S001', name: '示例供应商' },
      items_html:
        '<tr><td style="padding:6px;border:1px solid #ddd;">10</td><td style="padding:6px;border:1px solid #ddd;">PO001</td><td style="padding:6px;border:1px solid #ddd;text-align:right;">100</td><td style="padding:6px;border:1px solid #ddd;text-align:right;">888.00</td></tr>',
      printed_at: '2026-05-17 10:00:00',
    },
  },
}

function getGuide(code: string) {
  const key = (code || '').trim()
  return key ? TEMPLATE_GUIDES[key] : undefined
}

const activeGuide = ref<TemplateGuide | undefined>()
const previewGuide = ref<TemplateGuide | undefined>()

const formRef = ref<FormInstance>()
const rules: FormRules = {
  code: [{ required: true, message: () => t('system.printTemplates.pleaseInputCode'), trigger: 'blur' }],
  name: [{ required: true, message: () => t('system.printTemplates.pleaseInputName'), trigger: 'blur' }],
  template_type: [{ required: true, message: () => t('system.printTemplates.pleaseSelectType'), trigger: 'change' }],
  content: [{ required: true, message: () => t('system.printTemplates.pleaseInputContent'), trigger: 'blur' }],
}

async function reload(reset = false) {
  if (reset) query.offset = 0
  loading.value = true
  try {
    const res = await systemApi.listPrintTemplates({
      keyword: query.keyword || undefined,
      template_type: query.template_type || undefined,
      include_inactive: query.include_inactive,
      offset: query.offset,
      limit: query.limit,
    })
    items.value = res.items ?? []
    pager.page = Math.floor(query.offset / query.limit) + 1
    pager.total = res.items?.length === query.limit ? query.offset + query.limit + 1 : query.offset + items.value.length
  } finally {
    loading.value = false
  }
}

function onPage(p: number) {
  query.offset = (p - 1) * query.limit
  reload(false)
}

function openCreate() {
  dlg.id = 0
  dlg.form = { code: '', name: '', template_type: 'html', content: '', is_active: true }
  activeGuide.value = undefined
  dlg.open = true
}

function openEdit(row: PrintTemplateOut) {
  dlg.id = row.id
  dlg.form = { code: row.code, name: row.name, template_type: row.template_type, content: row.content, is_active: row.is_active }
  activeGuide.value = getGuide(row.code)
  dlg.open = true
}

watch(
  () => dlg.form.code,
  (v) => {
    activeGuide.value = getGuide(v)
  },
)

async function onSave() {
  const ok = await formRef.value?.validate().catch(() => false)
  if (!ok) return
  dlg.saving = true
  try {
    const payload = { ...dlg.form }
    if (dlg.id) await systemApi.updatePrintTemplate(dlg.id, payload)
    else await systemApi.createPrintTemplate(payload)
    dlg.open = false
    await reload(true)
  } finally {
    dlg.saving = false
  }
}

async function onDisable(row: PrintTemplateOut) {
  await systemApi.disablePrintTemplate(row.id)
  await reload(true)
}

function openPreview(row: PrintTemplateOut) {
  preview.id = row.id
  preview.code = row.code
  preview.html = ''
  previewGuide.value = getGuide(row.code)
  if (previewGuide.value) {
    preview.dataText = JSON.stringify(previewGuide.value.sample, null, 2)
  }
  preview.open = true
}

function applyPreviewSample() {
  if (!previewGuide.value) return
  preview.dataText = JSON.stringify(previewGuide.value.sample, null, 2)
}

function parseJson(s: string): any {
  const t = s.trim()
  if (!t) return {}
  return JSON.parse(t)
}

async function doRender() {
  if (!preview.id) return
  preview.loading = true
  try {
    const data = parseJson(preview.dataText)
    const res = await systemApi.renderPrintTemplate(preview.id, { data })
    preview.html = res.html || ''
  } catch {
    ElMessage.error(t('system.printTemplates.renderFailed'))
  } finally {
    preview.loading = false
  }
}

function openPrintWindow() {
  if (!preview.html) return
  openPrintHtmlWindow(preview.html, { title: `print_template_${preview.code || preview.id}` })
}

async function exportPdf() {
  if (!preview.id || preview.exporting) return
  preview.exporting = true
  try {
    const data = parseJson(preview.dataText)
    const res = await systemApi.renderPrintTemplatePdf(preview.id, { data })
    const blob = await http.request<Blob>({ url: `/files/${res.attachment_id}`, method: 'GET', params: { download: true }, responseType: 'blob' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = res.filename || `template_${preview.id}.pdf`
    document.body.appendChild(a)
    a.click()
    a.remove()
    URL.revokeObjectURL(url)
    ElMessage.success(t('system.printTemplates.pdfExported'))
  } catch {
    // handled
  } finally {
    preview.exporting = false
  }
}

onMounted(() => reload(true))
</script>
