<template>
  <AdminPage :title="t('production.orderImport.title')">
    <div class="mb-4 flex items-center gap-3">
      <el-button @click="router.back()">{{ t('production.common.back') }}</el-button>
      <h1 class="text-lg font-semibold">{{ t('production.orderImport.excelImport') }}</h1>
    </div>

    <el-row :gutter="20">
      <el-col :xs="24" :lg="14">
        <el-card>
          <el-form label-width="100px" @submit.prevent>
            <el-form-item>
              <el-button type="success" @click="onDownloadTemplate">{{ t('production.orderImport.downloadTemplate') }}</el-button>
            </el-form-item>

            <el-form-item label="订单名称" required>
              <el-input v-model="form.order_name" :placeholder="t('production.orderImport.orderNamePlaceholder')" maxlength="200" />
            </el-form-item>

            <el-form-item label="客户名称" required>
              <el-select
                v-model="form.customer_id"
                filterable
                :placeholder="t('production.orderImport.customerPlaceholder')"
                style="width: 100%"
                :loading="customersLoading"
                @change="onCustomerChange"
              >
                <el-option
                  v-for="c in customers"
                  :key="c.id"
                  :label="c.name"
                  :value="c.id"
                />
              </el-select>
            </el-form-item>

            <el-form-item label="客户电话">
              <el-input v-model="customerInfo.contact_phone" :placeholder="t('production.orderImport.customerPhonePlaceholder')" readonly />
            </el-form-item>

            <el-form-item label="联系人">
              <el-input v-model="customerInfo.contact_name" :placeholder="t('production.orderImport.customerPhonePlaceholder')" readonly />
            </el-form-item>

            <el-form-item label="客户地址">
              <el-input v-model="customerInfo.address" :placeholder="t('production.orderImport.customerPhonePlaceholder')" readonly />
            </el-form-item>

            <el-form-item label="交货时间">
              <el-date-picker
                v-model="form.due_date"
                type="date"
                value-format="YYYY-MM-DD"
                placeholder="选择交期"
                style="width: 100%"
              />
            </el-form-item>

            <el-form-item label="订单号">
              <el-input v-model="form.order_code" :placeholder="t('production.orderImport.orderCodePlaceholder')" maxlength="64" />
            </el-form-item>

            <el-form-item label="备注">
              <el-input v-model="form.remark" type="textarea" :rows="2" :placeholder="t('production.orderImport.remarkPlaceholder')" maxlength="500" />
            </el-form-item>

            <el-form-item label="选择文件" required>
              <el-upload
                drag
                accept=".xlsx,.xls"
                :auto-upload="false"
                :limit="1"
                :on-change="onFileChange"
                :on-remove="() => (form.file = null)"
              >
                <div class="text-sm text-zinc-500">{{ t('production.orderImport.dragHint') }}</div>
                <div class="text-xs text-zinc-400 mt-1">支持 .xlsx、.xls；表头：产品名称、型号名称、数量等</div>
              </el-upload>
            </el-form-item>

            <el-form-item label="导入选项">
              <el-checkbox v-model="form.auto_create_product">{{ t('production.orderImport.autoCreateProduct') }}</el-checkbox>
              <el-checkbox v-model="form.auto_create_sku" class="ml-4">{{ t('production.orderImport.autoCreateSku') }}</el-checkbox>
            </el-form-item>

            <el-form-item label="默认工价">
              <el-input-number v-model="form.default_unit_price" :min="0" :precision="2" :step="0.1" />
              <span class="ml-2 text-xs text-zinc-500">新建型号时，各工序统一使用该单价（元/件）</span>
            </el-form-item>

            <el-form-item>
              <el-button type="primary" :loading="submitting" @click="onSubmit">{{ t('production.orderImport.startImport') }}</el-button>
              <el-button @click="onReset">{{ t('production.orderImport.reset') }}</el-button>
            </el-form-item>
          </el-form>

          <div v-if="result" class="mt-4 space-y-3 border-t pt-4">
            <el-alert
              :title="resultTitle"
              :type="result.errors.length ? 'warning' : 'success'"
              show-icon
            />
            <div v-if="result.created_orders.length" class="text-sm">
              已创建订单：
              <el-link
                v-for="o in result.created_orders"
                :key="o.id"
                type="primary"
                class="mr-3"
                @click="router.push('/production/orders')"
              >
                {{ o.code }}
              </el-link>
            </div>
            <div v-if="result.warnings.length" class="max-h-32 overflow-y-auto">
              <div v-for="w in result.warnings" :key="'w' + w.row + w.message" class="text-xs text-amber-600 py-1">
                第 {{ w.row }} 行：{{ w.message }}
              </div>
            </div>
            <div v-if="result.errors.length" class="max-h-48 overflow-y-auto">
              <div v-for="e in result.errors" :key="'e' + e.row + e.message" class="text-xs text-red-500 py-1">
                第 {{ e.row }} 行：{{ e.message }}
              </div>
            </div>
          </div>
        </el-card>
      </el-col>

      <el-col :xs="24" :lg="10">
        <el-card class="mb-4">
          <template #header><span class="font-medium">{{ t('production.orderImport.importInstructions') }}</span></template>
          <ul class="text-sm text-zinc-600 space-y-2 list-disc pl-4">
            <li>在左侧填写<strong>{{ t('production.orderImport.orderName') }}</strong>并<strong>选择客户</strong>，客户电话、地址等将自动带出。</li>
            <li>Excel 仅需填写<strong>明细</strong>：产品名称、型号名称、数量；可选颜色、材料、规格、行备注。</li>
            <li>产品名称支持「产品-型号」合并写法（如「沙发-三人位」），型号名称列可留空。</li>
            <li>产品/型号<strong>编号由系统</strong>根据名称自动匹配；不存在时可勾选自动创建。</li>
            <li>新建型号将按产品默认工艺路线批量创建工序工价（默认 {{ form.default_unit_price }} 元/件）。</li>
            <li>导入后订单为<strong>草稿</strong>，需审核通过后创建生产计划，在计划中齐套检查并<strong>确认下发</strong>后才会生成工单。</li>
          </ul>
        </el-card>
        <el-card>
          <template #header><span class="font-medium text-amber-700">{{ t('production.orderImport.noticeTitle') }}</span></template>
          <ul class="text-sm text-zinc-600 space-y-2 list-disc pl-4">
            <li>导入前建议备份重要数据。</li>
            <li>数量列必须为大于 0 的整数。</li>
            <li>导入过程中请勿关闭页面。</li>
            <li>规格字段会参与型号匹配，请与系统中已有型号保持一致。</li>
          </ul>
        </el-card>
      </el-col>
    </el-row>
  </AdminPage>
</template>

<script setup lang="ts">
import AdminPage from '@/components/admin/AdminPage.vue'
import { computed, onMounted, reactive, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { productionApi, type CustomerOut, type OrderImportResult } from '@/api/production'

const { t } = useI18n()
const router = useRouter()
const customers = ref<CustomerOut[]>([])
const customersLoading = ref(false)
const submitting = ref(false)
const result = ref<OrderImportResult | null>(null)

const form = reactive({
  order_name: '',
  customer_id: null as number | null,
  due_date: '' as string | '',
  order_code: '',
  remark: '',
  file: null as File | null,
  auto_create_product: true,
  auto_create_sku: true,
  default_unit_price: 1,
})

const customerInfo = reactive({
  contact_name: '',
  contact_phone: '',
  address: '',
  code: '',
})

const resultTitle = computed(() => {
  if (!result.value) return ''
  const r = result.value
  return `导入完成：成功 ${r.lines_success} 行明细，创建 ${r.orders_created} 张订单，失败 ${r.errors.length} 条`
})

async function loadCustomers() {
  customersLoading.value = true
  try {
    const all: CustomerOut[] = []
    const limit = 200
    let offset = 0
    for (;;) {
      const res = await productionApi.listCustomers({ offset, limit, include_inactive: false })
      all.push(...(res.items || []))
      if (!res.items?.length || res.items.length < limit) break
      offset += limit
    }
    customers.value = all
  } finally {
    customersLoading.value = false
  }
}

async function onCustomerChange(id: number | null) {
  customerInfo.contact_name = ''
  customerInfo.contact_phone = ''
  customerInfo.address = ''
  customerInfo.code = ''
  if (!id) return
  try {
    const c = await productionApi.getCustomer(id)
    customerInfo.contact_name = c.contact_name || ''
    customerInfo.contact_phone = c.contact_phone || ''
    customerInfo.address = c.address || ''
    customerInfo.code = c.code
  } catch {
    ElMessage.error(t('production.orderImport.loadCustomerFailed'))
  }
}

function onFileChange(uploadFile: { raw?: File }) {
  const raw = uploadFile.raw
  if (!raw) {
    form.file = null
    return
  }
  // 确保上传文件带 .xlsx 扩展名，避免后端校验失败
  if (!raw.name.toLowerCase().endsWith('.xlsx') && !raw.name.toLowerCase().endsWith('.xls')) {
    form.file = new File([raw], `${raw.name || 'import'}.xlsx`, { type: raw.type || 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' })
  } else {
    form.file = raw
  }
}

async function onDownloadTemplate() {
  try {
    const blob = await productionApi.downloadOrderImportTemplate()
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = 'order_import_template.xlsx'
    document.body.appendChild(a)
    a.click()
    a.remove()
    URL.revokeObjectURL(url)
  } catch {
    ElMessage.error(t('production.orderImport.downloadTemplateFailed'))
  }
}

async function onSubmit() {
  if (!form.order_name.trim()) {
    ElMessage.warning(t('production.orderImport.pleaseInputOrderName'))
    return
  }
  if (!form.customer_id) {
    ElMessage.warning(t('production.orderImport.pleaseSelectCustomer'))
    return
  }
  if (!form.file) {
    ElMessage.warning(t('production.orderImport.pleaseSelectFile'))
    return
  }
  submitting.value = true
  result.value = null
  try {
    result.value = await productionApi.importOrdersExcel({
      file: form.file,
      customer_id: form.customer_id,
      order_name: form.order_name.trim(),
      due_date: form.due_date || undefined,
      remark: form.remark.trim() || undefined,
      order_code: form.order_code.trim() || undefined,
      auto_create_product: form.auto_create_product,
      auto_create_sku: form.auto_create_sku,
      default_unit_price: form.default_unit_price,
    })
    if (result.value.orders_created > 0) {
      ElMessage.success(`已创建订单 ${result.value.created_orders[0]?.code || ''}`)
    }
  } finally {
    submitting.value = false
  }
}

function onReset() {
  form.order_name = ''
  form.customer_id = null
  form.due_date = ''
  form.order_code = ''
  form.remark = ''
  form.file = null
  form.auto_create_product = true
  form.auto_create_sku = true
  form.default_unit_price = 1
  customerInfo.contact_name = ''
  customerInfo.contact_phone = ''
  customerInfo.address = ''
  customerInfo.code = ''
  result.value = null
}

onMounted(() => {
  loadCustomers()
})
</script>
