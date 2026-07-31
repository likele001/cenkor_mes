<template>
  <el-dialog
    :model-value="modelValue"
    :title="status === 'draft' ? t('production.orders.editTitleDraft') : t('production.orders.editTitleConfirmed')"
    width="760px"
    destroy-on-close
    @update:model-value="$emit('update:modelValue', $event)"
    @opened="loadOptions"
  >
    <div v-loading="optionsLoading">
      <el-alert
        v-if="orderPlanLocked"
        type="warning"
        :closable="false"
        show-icon
        class="mb-3"
        :title="t('production.orders.planLockedEditAlert')"
      />
      <el-form v-if="form" label-width="96px">
        <el-form-item :label="t('production.orders.customerLabel')" required>
          <el-select v-model="form.customer_id" filterable placeholder="客户" style="width: 100%" :disabled="status !== 'draft'">
            <el-option v-for="c in customers" :key="c.id" :label="partyOptionLabel(c)" :value="c.id" />
          </el-select>
        </el-form-item>
        <el-form-item :label="t('production.orders.code')" required>
          <el-input v-model="form.code" maxlength="64" show-word-limit :disabled="status !== 'draft'" />
        </el-form-item>
        <el-form-item :label="t('production.orders.dueDate')">
          <el-date-picker v-model="form.due_date" type="date" value-format="YYYY-MM-DD" style="width: 100%" :disabled="status !== 'draft'" />
        </el-form-item>
        <el-form-item :label="t('production.common.remark')">
          <el-input v-model="form.remark" type="textarea" :rows="2" />
        </el-form-item>
        <el-form-item :label="t('production.orders.productSku')" required>
          <div v-if="!orderPlanLocked" class="mb-2">
            <el-button size="small" @click="addLine">{{ t('production.orders.addSkuRow') }}</el-button>
          </div>
          <el-table class="w-full" :data="lines" border size="small">
            <el-table-column label="#" width="50">
              <template #default="{ $index }">{{ $index + 1 }}</template>
            </el-table-column>
            <el-table-column v-if="status === 'confirmed'" label="状态" width="100">
              <template #default="{ row }">
                <el-tag v-if="row.locked" type="warning" size="small">{{ row.lock_reason || '锁定' }}</el-tag>
                <el-tag v-else type="success" size="small">可改</el-tag>
              </template>
            </el-table-column>
            <el-table-column :label="t('production.orders.productSku')" min-width="280">
              <template #default="{ row }">
                <el-select v-model="row.sku_id" filterable :placeholder="t('production.orders.skuPlaceholder')" style="width: 100%" :disabled="row.locked || status !== 'draft'">
                  <el-option v-for="s in skus" :key="s.id" :label="orderSkuOptionLabel(s)" :value="s.id">
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
                <el-button size="small" type="danger" link :disabled="lines.length <= 1 || row.locked || orderPlanLocked" @click="removeLine($index)">删</el-button>
              </template>
            </el-table-column>
          </el-table>
          <p v-if="status === 'confirmed' || status === 'producing'" class="mt-2 text-xs text-zinc-500">
            已审核/生产中订单不可更换型号；未下发投产或未派工锁定前可改数量；已有工单时数量将同步任务。
          </p>
        </el-form-item>
      </el-form>
    </div>
    <template #footer>
      <el-button @click="$emit('update:modelValue', false)">{{ t('production.common.cancel') }}</el-button>
      <el-button type="primary" :loading="saving" @click="submit">{{ t('production.common.save') }}</el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { reactive, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { ElMessage } from 'element-plus'
import { productionApi, type CustomerOut, type OrderOut } from '@/api/production'
import { orderSkuOptionLabel, partyOptionLabel, type OrderSkuOption } from '@/utils/display'

type EditLine = {
  id?: number | null
  sku_id: number | null
  qty: number
  remark: string
  locked?: boolean
  lock_reason?: string | null
}

const props = defineProps<{
  modelValue: boolean
  editOrder: OrderOut | null
}>()

const emit = defineEmits<{
  'update:modelValue': [value: boolean]
  'updated': []
}>()

const { t } = useI18n()
const optionsLoading = ref(false)
const saving = ref(false)
const customers = ref<CustomerOut[]>([])
const skus = ref<OrderSkuOption[]>([])
const status = ref('draft')
const orderPlanLocked = ref(false)
const editId = ref(0)

const form = reactive<{
  customer_id: number | null
  code: string
  due_date: string
  remark: string
} | null>(null)

const lines = reactive<EditLine[]>([])

async function loadOptions() {
  if (!props.editOrder) return
  editId.value = props.editOrder.id
  status.value = props.editOrder.status
  orderPlanLocked.value = false
  optionsLoading.value = true
  try {
    const [opts, ord] = await Promise.all([
      productionApi.fetchOrderFormOptions(),
      productionApi.getOrder(editId.value),
    ])
    customers.value = (opts.customers || []) as CustomerOut[]
    skus.value = opts.skus || []
    if (ord.status !== 'draft' && ord.status !== 'confirmed' && ord.status !== 'producing') {
      ElMessage.warning('当前订单状态不可编辑')
      emit('update:modelValue', false)
      return
    }
    status.value = ord.status
    orderPlanLocked.value = !!ord.order_plan_locked
    Object.assign(form as NonNullable<typeof form>, {
      customer_id: ord.customer_id,
      code: ord.code,
      due_date: ord.due_date || '',
      remark: ord.remark || '',
    })
    lines.splice(0, lines.length, ...(ord.items || []).map((it) => ({
      id: it.id,
      sku_id: it.sku_id,
      qty: it.qty,
      remark: it.remark || '',
      locked: it.locked,
      lock_reason: it.lock_reason,
    })))
    if (!lines.length) {
      lines.push({ sku_id: null, qty: 1, remark: '' })
    }
  } finally {
    optionsLoading.value = false
  }
}

function addLine() {
  lines.push({ sku_id: null, qty: 1, remark: '' })
}

function removeLine(idx: number) {
  if (lines.length <= 1) return
  lines.splice(idx, 1)
}

async function submit() {
  if (!form || !editId.value) return
  if (status.value === 'draft') {
    if (!form.customer_id) {
      ElMessage.warning('请选择客户')
      return
    }
    if (!form.code.trim()) {
      ElMessage.warning('请输入订单号')
      return
    }
  }
  const payload: Parameters<typeof productionApi.updateOrder>[1] = {
    remark: form.remark?.trim() || undefined,
  }
  if (status.value === 'draft') {
    payload.customer_id = form.customer_id
    payload.code = form.code.trim()
    payload.due_date = form.due_date || undefined
  }
  if (!orderPlanLocked.value) {
    const rows = lines
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
  saving.value = true
  try {
    await productionApi.updateOrder(editId.value, payload)
    ElMessage.success('已保存')
    emit('update:modelValue', false)
    emit('updated')
  } finally {
    saving.value = false
  }
}
</script>
