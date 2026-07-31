<template>
  <AdminPage :title="t('production.orders.title')">
    <template #actions>
      <div class="flex items-center gap-2 flex-wrap">
          <el-button :loading="exporting" @click="exportExcel">导出 Excel</el-button>
          <el-button type="primary" @click="openCreate">{{ t('production.orders.createOrder') }}</el-button>
          <el-button @click="router.push('/production/orders/import')">{{ t('production.orders.excelImport') }}</el-button>
          <el-input v-model="query.keyword" :placeholder="t('production.orders.searchCode')" clearable style="width: 220px" @keyup.enter="reload(true)" />
          <el-input-number v-model="query.customer_id" :min="1" :controls="false" :placeholder="t('production.orders.customerId')" style="width: 140px" @change="reload(true)" />
          <el-input-number v-model="query.opportunity_id" :min="1" :controls="false" placeholder="来源商机ID" style="width: 140px" @change="reload(true)" />
          <el-select v-model="query.status" clearable :placeholder="t('production.common.status')" style="width: 140px" @change="reload(true)">
            <el-option :label="t('production.orders.draft')" value="draft" />
            <el-option :label="t('production.orders.pendingConfirm')" value="pending_confirm" />
            <el-option :label="t('production.orders.confirmed')" value="confirmed" />
            <el-option :label="t('production.orders.producing')" value="producing" />
          </el-select>
          <el-button @click="reload(true)">刷新</el-button>
        </div>
    </template>

    <AdminDataTable
      :loading="loading"
      :empty="!loading && !items.length"
      :page-size="query.limit"
      :total="fakeTotal"
      :current-page="page"
      @page-change="onPageChange"
    >
      <template #table>
        <el-table class="hidden lg:block w-full" :data="items" border>
          <el-table-column prop="id" label="ID" width="90" />
          <el-table-column prop="code" :label="t('production.orders.code')" width="220" />
          <el-table-column :label="t('production.orders.customerLabel')" min-width="200">
            <template #default="{ row }">
              <span v-if="row.customer">{{ row.customer.name }}（{{ row.customer.code }}）</span>
              <span v-else>{{ t('production.common.customer') }}#{{ row.customer_id }}</span>
            </template>
          </el-table-column>
          <el-table-column :label="t('production.common.status')" width="120">
            <template #default="{ row }">
              <el-tag :type="statusTagType(row.status)">{{ statusLabel(row.status) }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="due_date" :label="t('production.orders.dueDate')" width="130" />
          <el-table-column prop="remark" :label="t('production.common.remark')" min-width="220" />
          <el-table-column prop="confirmed_at" :label="t('production.orders.confirmTime')" width="180" />
          <el-table-column :label="t('production.common.operation')" width="360" fixed="right">
            <template #default="{ row }">
              <el-button size="small" @click="openDetail(row.id)">{{ t('production.orders.detail') }}</el-button>
              <el-button
                size="small"
                :disabled="row.status !== 'draft' && row.status !== 'confirmed' && row.status !== 'producing'"
                @click="openEdit(row)"
              >
                编辑
              </el-button>
              <el-button
                v-if="row.status === 'pending_confirm'"
                size="small"
                type="warning"
                link
                @click="onReject(row.id)"
              >
                驳回
              </el-button>
              <el-button
                size="small"
                type="primary"
                :disabled="row.status !== 'draft' && row.status !== 'pending_confirm'"
                :loading="confirmingId === row.id"
                @click="onConfirm(row.id)"
              >
                审核通过
              </el-button>
            </template>
          </el-table-column>
        </el-table>
      </template>
      <template #mobile>
        <div class="lg:hidden space-y-3">
          <div v-for="row in items" :key="row.id" class="admin-mobile-row">
            <div class="admin-mobile-row__head">
              <div class="min-w-0">
                <div class="font-semibold text-el-primary truncate">{{ row.code }}</div>
                <div class="text-xs text-el-placeholder">ID {{ row.id }}</div>
              </div>
              <el-tag :type="statusTagType(row.status)" size="small">{{ statusLabel(row.status) }}</el-tag>
            </div>
            <dl class="admin-mobile-kv">
              <dt>客户</dt>
              <dd>
                <span v-if="row.customer">{{ row.customer.name }}（{{ row.customer.code }}）</span>
                <span v-else>{{ t('production.common.customer') }}#{{ row.customer_id }}</span>
              </dd>
              <dt>交期</dt>
              <dd>{{ row.due_date || '—' }}</dd>
              <dt>备注</dt>
              <dd>{{ row.remark || '—' }}</dd>
              <dt>确认时间</dt>
              <dd>{{ row.confirmed_at || '—' }}</dd>
            </dl>
            <div class="admin-mobile-actions">
              <el-button size="small" @click="openDetail(row.id)">{{ t('production.orders.detail') }}</el-button>
              <el-button
                size="small"
                :disabled="row.status !== 'draft' && row.status !== 'confirmed' && row.status !== 'producing'"
                @click="openEdit(row)"
              >
                编辑
              </el-button>
              <el-button
                size="small"
                type="primary"
                :disabled="row.status !== 'draft' && row.status !== 'pending_confirm'"
                :loading="confirmingId === row.id"
                @click="onConfirm(row.id)"
              >
                审核通过
              </el-button>
            </div>
          </div>
        </div>
      </template>
    </AdminDataTable>

    <template #extra>
    <el-dialog v-model="detail.open" :title="t('production.orders.detailTitle')" width="900px" destroy-on-close>
      <div v-loading="detail.loading">
        <el-descriptions v-if="detail.data" :column="3" border>
          <el-descriptions-item label="ID">{{ detail.data.id }}</el-descriptions-item>
          <el-descriptions-item :label="t('production.orders.code')">{{ detail.data.code }}</el-descriptions-item>
          <el-descriptions-item label="客户">
            <span v-if="detail.data.customer">{{ detail.data.customer.name }}（{{ detail.data.customer.code }}）</span>
            <span v-else>{{ t('production.common.customer') }}#{{ detail.data.customer_id }}</span>
          </el-descriptions-item>
          <el-descriptions-item label="状态">{{ statusLabel(detail.data.status) }}</el-descriptions-item>
          <el-descriptions-item :label="t('production.orders.dueDate')">{{ detail.data.due_date || '-' }}</el-descriptions-item>
          <el-descriptions-item label="确认时间">{{ detail.data.confirmed_at || '-' }}</el-descriptions-item>
          <el-descriptions-item v-if="detail.data.opportunity_id" label="来源商机">
            <router-link :to="{ name: 'production-customer-detail', params: { id: detail.data.customer_id }, query: { tab: 'opps' } }">
              {{ detail.data.opportunity_code || `#${detail.data.opportunity_id}` }}
            </router-link>
          </el-descriptions-item>
        </el-descriptions>

        <el-alert
          v-if="detail.data?.order_plan_locked"
          class="mt-3"
          type="warning"
          :closable="false"
          show-icon
          :title="t('production.orders.planLockedAlert')"
        />
        <el-table v-if="detail.data" class="hidden lg:block mt-4 w-full" :data="detail.data.items" border>
          <el-table-column prop="line_no" :label="t('production.orders.lineNo')" width="90" />
          <el-table-column v-if="detail.data.status === 'confirmed' || detail.data.status === 'producing'" :label="t('production.orders.lockedLabel')" width="120">
            <template #default="{ row }">
              <el-tag v-if="row.locked" type="warning" size="small">{{ row.lock_reason || '锁定' }}</el-tag>
              <span v-else class="text-zinc-400">—</span>
            </template>
          </el-table-column>
          <el-table-column :label="t('production.orders.productSku')" min-width="280">
            <template #default="{ row }">
              <template v-if="row.sku">
                <div class="font-medium">{{ row.sku.product_name || row.sku.name }}</div>
                <div class="text-xs text-zinc-500">{{ row.sku.sku_name || row.sku.display_label || row.sku.name }}</div>
              </template>
              <span v-else>{{ t('production.common.customer') }}#{{ row.sku_id }}</span>
            </template>
          </el-table-column>
          <el-table-column prop="qty" :label="t('production.orders.quantityLabel')" width="110" />
          <el-table-column prop="remark" :label="t('production.common.remark')" min-width="240" />
        </el-table>
        <div v-if="detail.data" class="lg:hidden space-y-3 mt-4">
          <div v-for="row in detail.data.items" :key="row.line_no" class="admin-mobile-row">
            <div class="text-xs text-el-placeholder">行 {{ row.line_no }}</div>
            <div v-if="row.sku" class="text-sm">
              <div class="font-medium">{{ row.sku.product_name || row.sku.name }}</div>
              <div class="text-xs text-zinc-500">{{ row.sku.sku_name || row.sku.display_label }}</div>
            </div>
            <div v-else class="font-medium text-sm">{{ t('production.common.customer') }}#{{ row.sku_id }}</div>
            <dl class="admin-mobile-kv mt-2">
              <dt>数量</dt>
              <dd>{{ row.qty }}</dd>
              <dt>备注</dt>
              <dd class="text-left">{{ row.remark || '—' }}</dd>
            </dl>
          </div>
        </div>
      </div>
      <template #footer>
        <el-button @click="detail.open = false">{{ t('production.common.close') }}</el-button>
      </template>
    </el-dialog>

    <!-- 新建订单（对接 POST /admin/production/orders） -->
    <el-dialog v-model="createDlg.open" :title="t('production.orders.createTitle')" width="720px" destroy-on-close @opened="loadCreateOptions">
      <div v-loading="createDlg.optionsLoading">
        <el-form label-width="96px">
          <el-form-item :label="t('production.orders.customerLabel')" required>
            <el-select v-model="createDlg.form.customer_id" filterable :placeholder="t('production.orders.customerPlaceholder')" style="width: 100%">
              <el-option
                v-for="c in createDlg.customers"
                :key="c.id"
                :label="partyOptionLabel(c)"
                :value="c.id"
              />
            </el-select>
          </el-form-item>
          <el-form-item :label="t('production.orders.code')">
            <el-input
              v-model="createDlg.form.code"
              :placeholder="t('production.orders.orderCodePlaceholder')"
              maxlength="64"
              show-word-limit
            />
            <div class="text-xs text-zinc-500 mt-1">编号按日递增（ORD+日期+序号）。保存后会占用序号，下次自动为 002、003…</div>
          </el-form-item>
          <el-form-item :label="t('production.orders.dueDate')">
            <el-date-picker
              v-model="createDlg.form.due_date"
              type="date"
              value-format="YYYY-MM-DD"
              :placeholder="t('production.orders.remarkPlaceholder')"
              style="width: 100%"
            />
          </el-form-item>
          <el-form-item :label="t('production.common.remark')">
            <el-input v-model="createDlg.form.remark" type="textarea" :rows="2" :placeholder="t('production.orders.remarkPlaceholder')" />
          </el-form-item>
          <el-form-item :label="t('production.orders.productSku')" required>
            <div class="mb-2">
              <el-button size="small" @click="addCreateLine">{{ t('production.orders.addSkuRow') }}</el-button>
            </div>
            <el-table class="w-full" :data="createDlg.lines" border size="small">
              <el-table-column label="#" width="50">
                <template #default="{ $index }">{{ $index + 1 }}</template>
              </el-table-column>
              <el-table-column :label="t('production.orders.productSku')" min-width="280">
                <template #default="{ row }">
                  <el-select
                    v-model="row.sku_id"
                    filterable
                    :placeholder="t('production.orders.skuPlaceholder')"
                    style="width: 100%"
                  >
                    <el-option v-for="s in createDlg.skus" :key="s.id" :label="orderSkuOptionLabel(s)" :value="s.id">
                      <div class="leading-tight py-0.5">
                        <div>{{ orderSkuOptionLabel(s) }}</div>
                        <div class="text-xs text-zinc-400">编码 {{ s.code }}</div>
                      </div>
                    </el-option>
                  </el-select>
                </template>
              </el-table-column>
              <el-table-column :label="t('production.orders.quantityLabelCol')" width="120">
                <template #default="{ row }">
                  <el-input-number v-model="row.qty" :min="1" :controls="false" class="!w-full" />
                </template>
              </el-table-column>
              <el-table-column :label="t('production.orders.rowRemarkLabel')" width="120">
                <template #default="{ row }">
                  <el-input v-model="row.remark" :placeholder="t('production.orders.remarkPlaceholder')" />
                </template>
              </el-table-column>
              <el-table-column label="" width="70" fixed="right">
                <template #default="{ $index }">
                  <el-button size="small" type="danger" link :disabled="createDlg.lines.length <= 1" @click="removeCreateLine($index)">删</el-button>
                </template>
              </el-table-column>
            </el-table>
          </el-form-item>
        </el-form>
      </div>
      <template #footer>
        <el-button @click="createDlg.open = false">{{ t('production.common.cancel') }}</el-button>
        <el-button type="primary" :loading="createDlg.saving" @click="submitCreate">{{ t('production.orders.saveDraft') }}</el-button>
      </template>
    </el-dialog>

    <!-- 编辑订单：草稿全改；已确认按行锁定 -->
    <el-dialog
      v-model="editDlg.open"
      :title="editDlg.status === 'draft' ? t('production.orders.editTitleDraft') : t('production.orders.editTitleConfirmed')"
      width="760px"
      destroy-on-close
      @opened="loadEditOptions"
    >
      <div v-loading="editDlg.optionsLoading">
        <el-alert
          v-if="editDlg.orderPlanLocked"
          type="warning"
          :closable="false"
          show-icon
          class="mb-3"
          :title="t('production.orders.planLockedEditAlert')"
        />
        <el-form v-if="editDlg.form" label-width="96px">
          <el-form-item :label="t('production.orders.customerLabel')" required>
            <el-select
              v-model="editDlg.form.customer_id"
              filterable
              placeholder="客户"
              style="width: 100%"
              :disabled="editDlg.status !== 'draft'"
            >
              <el-option
                v-for="c in editDlg.customers"
                :key="c.id"
                :label="partyOptionLabel(c)"
                :value="c.id"
              />
            </el-select>
          </el-form-item>
          <el-form-item :label="t('production.orders.code')" required>
            <el-input v-model="editDlg.form.code" maxlength="64" show-word-limit :disabled="editDlg.status !== 'draft'" />
          </el-form-item>
          <el-form-item :label="t('production.orders.dueDate')">
            <el-date-picker
              v-model="editDlg.form.due_date"
              type="date"
              value-format="YYYY-MM-DD"
              style="width: 100%"
              :disabled="editDlg.status !== 'draft'"
            />
          </el-form-item>
          <el-form-item :label="t('production.common.remark')">
            <el-input v-model="editDlg.form.remark" type="textarea" :rows="2" />
          </el-form-item>
          <el-form-item :label="t('production.orders.productSku')" required>
            <div v-if="!editDlg.orderPlanLocked" class="mb-2">
              <el-button size="small" @click="addEditLine">{{ t('production.orders.addSkuRow') }}</el-button>
            </div>
            <el-table class="w-full" :data="editDlg.lines" border size="small">
              <el-table-column label="#" width="50">
                <template #default="{ $index }">{{ $index + 1 }}</template>
              </el-table-column>
              <el-table-column v-if="editDlg.status === 'confirmed'" label="状态" width="100">
                <template #default="{ row }">
                  <el-tag v-if="row.locked" type="warning" size="small">{{ row.lock_reason || '锁定' }}</el-tag>
                  <el-tag v-else type="success" size="small">可改</el-tag>
                </template>
              </el-table-column>
              <el-table-column :label="t('production.orders.productSku')" min-width="280">
                <template #default="{ row }">
                  <el-select
                    v-model="row.sku_id"
                    filterable
                    :placeholder="t('production.orders.skuPlaceholder')"
                    style="width: 100%"
                    :disabled="row.locked || editDlg.status !== 'draft'"
                  >
                    <el-option v-for="s in editDlg.skus" :key="s.id" :label="orderSkuOptionLabel(s)" :value="s.id">
                      <div class="leading-tight py-0.5">
                        <div>{{ orderSkuOptionLabel(s) }}</div>
                        <div class="text-xs text-zinc-400">编码 {{ s.code }}</div>
                      </div>
                    </el-option>
                  </el-select>
                </template>
              </el-table-column>
              <el-table-column :label="t('production.orders.quantityLabelCol')" width="120">
                <template #default="{ row }">
                  <el-input-number v-model="row.qty" :min="1" :controls="false" class="!w-full" :disabled="row.locked" />
                </template>
              </el-table-column>
              <el-table-column label="行备注" min-width="100">
                <template #default="{ row }">
                  <el-input v-model="row.remark" :placeholder="t('production.orders.remarkPlaceholder')" :disabled="row.locked" />
                </template>
              </el-table-column>
              <el-table-column label="" width="70" fixed="right">
                <template #default="{ $index, row }">
                  <el-button
                    size="small"
                    type="danger"
                    link
                    :disabled="editDlg.lines.length <= 1 || row.locked || editDlg.orderPlanLocked"
                    @click="removeEditLine($index)"
                  >
                    删
                  </el-button>
                </template>
              </el-table-column>
            </el-table>
            <p v-if="editDlg.status === 'confirmed' || editDlg.status === 'producing'" class="mt-2 text-xs text-zinc-500">
              已审核/生产中订单不可更换型号；未下发投产或未派工锁定前可改数量；已有工单时数量将同步任务。
            </p>
          </el-form-item>
        </el-form>
      </div>
      <template #footer>
        <el-button @click="editDlg.open = false">{{ t('production.common.cancel') }}</el-button>
        <el-button type="primary" :loading="editDlg.saving" @click="submitEdit">{{ t('production.common.save') }}</el-button>
      </template>
    </el-dialog>
    </template>
  </AdminPage>
</template>

<script setup lang="ts">
import AdminPage from '@/components/admin/AdminPage.vue'
import AdminDataTable from '@/components/admin/AdminDataTable.vue'
import { computed, onMounted, reactive, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { productionApi, type CustomerOut, type OrderDetailOut, type OrderOut } from '@/api/production'
import { systemApi } from '@/api/system'
import { codeForSubmit } from '@/utils/code'
import { formatAutomationFeedback } from '@/utils/automationFeedback'
import { orderSkuOptionLabel, partyOptionLabel, type OrderSkuOption } from '@/utils/display'
import { useStatus } from '@/utils/status-maps'

const { t } = useI18n()
const { label: statusLabel, type: statusTagType } = useStatus('order')
const router = useRouter()
const loading = ref(false)
const exporting = ref(false)
const items = ref<OrderOut[]>([])
const confirmingId = ref<number | null>(null)
const query = reactive({ keyword: '', customer_id: null as number | null, opportunity_id: null as number | null, status: '', offset: 0, limit: 50 })

const page = computed(() => Math.floor(query.offset / query.limit) + 1)
const fakeTotal = computed(() => query.offset + items.value.length + (items.value.length === query.limit ? query.limit : 0))

const detail = reactive({
  open: false,
  loading: false,
  data: null as OrderDetailOut | null,
})

async function suggestedOrderCode() {
  try {
    const res = await systemApi.nextCode('order')
    return res.code
  } catch {
    return ''
  }
}

const createDlg = reactive({
  open: false,
  optionsLoading: false,
  saving: false,
  customers: [] as CustomerOut[],
  skus: [] as OrderSkuOption[],
  form: {
    customer_id: null as number | null,
    code: '',
    due_date: '' as string,
    remark: '',
  },
  lines: [] as { sku_id: number | null; qty: number; remark: string }[],
})

type EditLine = {
  id?: number | null
  sku_id: number | null
  qty: number
  remark: string
  locked?: boolean
  lock_reason?: string | null
}

const editDlg = reactive({
  open: false,
  editId: 0,
  status: 'draft' as string,
  orderPlanLocked: false,
  optionsLoading: false,
  saving: false,
  customers: [] as CustomerOut[],
  skus: [] as OrderSkuOption[],
  form: null as { customer_id: number; code: string; due_date: string; remark: string } | null,
  lines: [] as EditLine[],
})



async function onReject(orderId: number) {
  const reason = await ElMessageBox.prompt('请输入驳回原因', '驳回订单', { inputPattern: /.+/, inputErrorMessage: '请填写原因' })
    .then((r) => r.value)
    .catch(() => null)
  if (!reason) return
  await productionApi.rejectOrder(orderId, reason)
  ElMessage.success('已驳回')
  await reload(false)
}

async function reload(reset = false) {
  if (reset) query.offset = 0
  loading.value = true
  try {
    const res = await productionApi.listOrders({
      keyword: query.keyword || undefined,
      customer_id: query.customer_id || undefined,
      opportunity_id: query.opportunity_id || undefined,
      status: query.status || undefined,
      offset: query.offset,
      limit: query.limit,
    })
    items.value = res.items
  } finally {
    loading.value = false
  }
}

function onPageChange(p: number) {
  query.offset = (p - 1) * query.limit
  reload(false)
}

async function openDetail(orderId: number) {
  detail.open = true
  detail.loading = true
  detail.data = null
  try {
    detail.data = await productionApi.getOrder(orderId)
  } finally {
    detail.loading = false
  }
}

async function onConfirm(orderId: number) {
  if (confirmingId.value) return
  const ok = await ElMessageBox.confirm('确认审核通过该订单？通过后可创建生产计划，在计划中齐套检查并下发投产。', '审核订单', {
    type: 'warning',
  })
    .then(() => true)
    .catch(() => false)
  if (!ok) return
  confirmingId.value = orderId
  try {
    const res = await productionApi.confirmOrder(orderId)
    const autoMsg = formatAutomationFeedback(res)
    ElMessage.success(autoMsg ? `订单已审核。${autoMsg}` : '订单已审核，请前往生产计划排产并确认下发')
    await reload(false)
  } finally {
    confirmingId.value = null
  }
}

async function openCreate() {
  createDlg.form = {
    customer_id: null,
    code: await suggestedOrderCode(),
    due_date: '',
    remark: '',
  }
  createDlg.lines = [{ sku_id: null, qty: 1, remark: '' }]
  createDlg.open = true
}

async function loadCreateOptions() {
  createDlg.optionsLoading = true
  try {
    const res = await productionApi.fetchOrderFormOptions()
    createDlg.customers = (res.customers || []) as CustomerOut[]
    createDlg.skus = res.skus || []
    if (!createDlg.form.code.trim()) createDlg.form.code = await suggestedOrderCode()
  } finally {
    createDlg.optionsLoading = false
  }
}

function addCreateLine() {
  createDlg.lines.push({ sku_id: null, qty: 1, remark: '' })
}

function removeCreateLine(idx: number) {
  if (createDlg.lines.length <= 1) return
  createDlg.lines.splice(idx, 1)
}

async function submitCreate() {
  if (!createDlg.form.customer_id) {
    ElMessage.warning('请选择客户')
    return
  }
  const rows = createDlg.lines
    .filter((row) => row.sku_id != null && Number.isFinite(Number(row.qty)))
    .map((row, idx) => {
      const q = Math.max(1, Math.floor(Number(row.qty)))
      return {
      line_no: idx + 1,
      sku_id: row.sku_id as number,
      qty: q,
      remark: row.remark?.trim() ? row.remark.trim() : undefined,
    }})
  if (!rows.length) {
    ElMessage.warning('请至少填写一行型号与数量')
    return
  }
  createDlg.saving = true
  try {
    await productionApi.createOrder({
      customer_id: createDlg.form.customer_id as number,
      code: codeForSubmit(createDlg.form.code) || undefined,
      due_date: createDlg.form.due_date || undefined,
      remark: createDlg.form.remark?.trim() || undefined,
      items: rows,
    })
    ElMessage.success('订单已创建（草稿）')
    createDlg.open = false
    await reload(true)
  } finally {
    createDlg.saving = false
  }
}

function openEdit(row: OrderOut) {
  if (row.status !== 'draft' && row.status !== 'confirmed' && row.status !== 'producing') {
    ElMessage.warning('当前状态不可编辑')
    return
  }
  editDlg.editId = row.id
  editDlg.status = row.status
  editDlg.orderPlanLocked = false
  editDlg.form = null
  editDlg.lines = []
  editDlg.open = true
}

async function loadEditOptions() {
  if (!editDlg.editId) return
  editDlg.optionsLoading = true
  try {
    const [opts, ord] = await Promise.all([productionApi.fetchOrderFormOptions(), productionApi.getOrder(editDlg.editId)])
    editDlg.customers = (opts.customers || []) as CustomerOut[]
    editDlg.skus = opts.skus || []
    if (ord.status !== 'draft' && ord.status !== 'confirmed' && ord.status !== 'producing') {
      ElMessage.warning('当前订单状态不可编辑')
      editDlg.open = false
      return
    }
    editDlg.status = ord.status
    editDlg.orderPlanLocked = !!ord.order_plan_locked
    editDlg.form = {
      customer_id: ord.customer_id,
      code: ord.code,
      due_date: ord.due_date || '',
      remark: ord.remark || '',
    }
    editDlg.lines = (ord.items || []).map((it) => ({
      id: it.id,
      sku_id: it.sku_id,
      qty: it.qty,
      remark: it.remark || '',
      locked: it.locked,
      lock_reason: it.lock_reason,
    }))
    if (!editDlg.lines.length) {
      editDlg.lines = [{ sku_id: null, qty: 1, remark: '' }]
    }
  } finally {
    editDlg.optionsLoading = false
  }
}

function addEditLine() {
  editDlg.lines.push({ sku_id: null, qty: 1, remark: '' })
}

function removeEditLine(idx: number) {
  if (editDlg.lines.length <= 1) return
  editDlg.lines.splice(idx, 1)
}

async function submitEdit() {
  if (!editDlg.form || !editDlg.editId) return
  if (editDlg.status === 'draft') {
    if (!editDlg.form.customer_id) {
      ElMessage.warning('请选择客户')
      return
    }
    if (!editDlg.form.code.trim()) {
      ElMessage.warning('请输入订单号')
      return
    }
  }
  const payload: Parameters<typeof productionApi.updateOrder>[1] = {
    remark: editDlg.form.remark?.trim() || undefined,
  }
  if (editDlg.status === 'draft') {
    payload.customer_id = editDlg.form.customer_id
    payload.code = editDlg.form.code.trim()
    payload.due_date = editDlg.form.due_date || undefined
  }
  if (!editDlg.orderPlanLocked) {
    const rows = editDlg.lines
      .filter((row) => row.sku_id != null && Number.isFinite(Number(row.qty)))
      .map((row, idx) => {
        const q = Math.max(1, Math.floor(Number(row.qty)))
        return {
          id: row.id ?? undefined,
          line_no: idx + 1,
          sku_id: row.sku_id as number,
          qty: q,
          remark: row.remark?.trim() ? row.remark.trim() : undefined,
        }
      })
    if (!rows.length) {
      ElMessage.warning('请至少填写一行型号与数量')
      return
    }
    payload.items = rows
  }
  editDlg.saving = true
  try {
    await productionApi.updateOrder(editDlg.editId, payload)
    ElMessage.success('已保存')
    editDlg.open = false
    await reload(false)
  } finally {
    editDlg.saving = false
  }
}

async function exportExcel() {
  if (exporting.value) return
  exporting.value = true
  try {
    const blob = await productionApi.exportOrders({})
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `orders_${new Date().toISOString().slice(0, 10)}.xlsx`
    a.click()
    URL.revokeObjectURL(url)
    ElMessage.success('导出成功')
  } catch { /* http 已提示 */
  } finally { exporting.value = false }
}

onMounted(() => reload(true))
</script>
