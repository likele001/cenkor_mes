<template>
  <el-dialog
    :model-value="modelValue"
    :title="t('production.orders.createTitle')"
    width="720px"
    destroy-on-close
    @update:model-value="$emit('update:modelValue', $event)"
    @opened="loadOptions"
  >
    <div v-loading="optionsLoading">
      <el-form label-width="96px">
        <el-form-item :label="t('production.orders.customerLabel')" required>
          <el-select v-model="form.customer_id" filterable :placeholder="t('production.orders.customerPlaceholder')" style="width: 100%">
            <el-option
              v-for="c in customers"
              :key="c.id"
              :label="partyOptionLabel(c)"
              :value="c.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item :label="t('production.orders.code')">
          <el-input
            v-model="form.code"
            :placeholder="t('production.orders.orderCodePlaceholder')"
            maxlength="64"
            show-word-limit
          />
          <div class="text-xs text-zinc-500 mt-1">编号按日递增（ORD+日期+序号）。保存后会占用序号，下次自动为 002、003…</div>
        </el-form-item>
        <el-form-item :label="t('production.orders.dueDate')">
          <el-date-picker
            v-model="form.due_date"
            type="date"
            value-format="YYYY-MM-DD"
            :placeholder="t('production.orders.remarkPlaceholder')"
            style="width: 100%"
          />
        </el-form-item>
        <el-form-item :label="t('production.common.remark')">
          <el-input v-model="form.remark" type="textarea" :rows="2" :placeholder="t('production.orders.remarkPlaceholder')" />
        </el-form-item>
        <el-form-item :label="t('production.orders.productSku')" required>
          <div class="mb-2">
            <el-button size="small" @click="addLine">{{ t('production.orders.addSkuRow') }}</el-button>
          </div>
          <el-table class="w-full" :data="lines" border size="small">
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
                <el-button size="small" type="danger" link :disabled="lines.length <= 1" @click="removeLine($index)">删</el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-form-item>
      </el-form>
    </div>
    <template #footer>
      <el-button @click="$emit('update:modelValue', false)">{{ t('production.common.cancel') }}</el-button>
      <el-button type="primary" :loading="saving" @click="submit">{{ t('production.orders.saveDraft') }}</el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { reactive, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { ElMessage } from 'element-plus'
import { productionApi, type CustomerOut } from '@/api/production'
import { systemApi } from '@/api/system'
import { codeForSubmit } from '@/utils/code'
import { orderSkuOptionLabel, partyOptionLabel, type OrderSkuOption } from '@/utils/display'

defineProps<{
  modelValue: boolean
}>()

const emit = defineEmits<{
  'update:modelValue': [value: boolean]
  'created': []
}>()

const { t } = useI18n()
const optionsLoading = ref(false)
const saving = ref(false)
const customers = ref<CustomerOut[]>([])
const skus = ref<OrderSkuOption[]>([])

const form = reactive({
  customer_id: null as number | null,
  code: '',
  due_date: '' as string,
  remark: '',
})

const lines = reactive<{ sku_id: number | null; qty: number; remark: string }[]>([])

async function suggestedOrderCode() {
  try {
    const res = await systemApi.nextCode('order')
    return res.code
  } catch {
    return ''
  }
}

async function loadOptions() {
  optionsLoading.value = true
  try {
    const res = await productionApi.fetchOrderFormOptions()
    customers.value = (res.customers || []) as CustomerOut[]
    skus.value = res.skus || []
    if (!form.code.trim()) form.code = await suggestedOrderCode()
  } finally {
    optionsLoading.value = false
  }
}

/** Called by parent to initialize form state before opening */
async function resetForm() {
  form.customer_id = null
  form.code = await suggestedOrderCode()
  form.due_date = ''
  form.remark = ''
  lines.splice(0, lines.length, { sku_id: null, qty: 1, remark: '' })
}

function addLine() {
  lines.push({ sku_id: null, qty: 1, remark: '' })
}

function removeLine(idx: number) {
  if (lines.length <= 1) return
  lines.splice(idx, 1)
}

async function submit() {
  if (!form.customer_id) {
    ElMessage.warning('请选择客户')
    return
  }
  const rows = lines
    .filter((row) => row.sku_id != null && Number.isFinite(Number(row.qty)))
    .map((row, idx) => {
      const q = Math.max(1, Math.floor(Number(row.qty)))
      return {
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
  saving.value = true
  try {
    await productionApi.createOrder({
      customer_id: form.customer_id as number,
      code: codeForSubmit(form.code) || undefined,
      due_date: form.due_date || undefined,
      remark: form.remark?.trim() || undefined,
      items: rows,
    })
    ElMessage.success('订单已创建（草稿）')
    emit('update:modelValue', false)
    emit('created')
  } finally {
    saving.value = false
  }
}

defineExpose({ resetForm })
</script>
