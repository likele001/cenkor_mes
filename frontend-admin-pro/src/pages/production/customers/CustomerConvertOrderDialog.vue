<script setup lang="ts">
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { ElMessage } from 'element-plus'
import type { OrderSkuOption } from '@/api/production'
import { orderSkuOptionLabel } from '@/utils/display'

const { t } = useI18n()

const props = defineProps<{
  modelValue: boolean
  dueDate: string | null
  remark: string
  skus: OrderSkuOption[]
}>()

const emit = defineEmits<{
  (e: 'update:modelValue', v: boolean): void
  (e: 'submit', payload: { due_date: string | null; remark: string; items: { line_no: number; sku_id: number; qty: number; remark: string | null }[] }): void
}>()

const saving = ref(false)
const localDueDate = ref(props.dueDate)
const localRemark = ref(props.remark)
const lines = ref<{ sku_id: number | null; qty: number; remark: string }[]>([
  { sku_id: null, qty: 1, remark: '' },
])

function handleSubmit() {
  const items = lines.value
    .filter((row) => row.sku_id != null && Number(row.qty) > 0)
    .map((row, idx) => ({
      line_no: idx + 1,
      sku_id: row.sku_id as number,
      qty: Number(row.qty),
      remark: row.remark || null,
    }))
  if (!items.length) {
    ElMessage.warning('请添加至少一行 SKU')
    return
  }
  saving.value = true
  emit('submit', {
    due_date: localDueDate.value,
    remark: localRemark.value || '',
    items,
  })
}

function addLine() {
  lines.value.push({ sku_id: null, qty: 1, remark: '' })
}

function removeLine(idx: number) {
  if (lines.value.length > 1) lines.value.splice(idx, 1)
}
</script>

<template>
  <el-dialog
    :model-value="modelValue"
    @update:model-value="emit('update:modelValue', $event)"
    :title="t('production.customers.convertOrder')"
    width="640px"
    destroy-on-close
  >
    <el-form label-width="80px">
      <el-form-item label="交期">
        <el-date-picker v-model="localDueDate" type="date" value-format="YYYY-MM-DD" style="width: 100%" />
      </el-form-item>
      <el-form-item label="备注">
        <el-input v-model="localRemark" type="textarea" :rows="2" />
      </el-form-item>
      <el-form-item label="明细">
        <div class="space-y-2 w-full">
          <div v-for="(row, idx) in lines" :key="idx" class="flex gap-2 items-center">
            <el-select v-model="row.sku_id" filterable placeholder="SKU" style="flex: 1">
              <el-option v-for="s in props.skus" :key="s.id" :label="orderSkuOptionLabel(s)" :value="s.id" />
            </el-select>
            <el-input-number v-model="row.qty" :min="1" style="width: 120px" />
            <el-button v-if="lines.length > 1" type="danger" link @click="removeLine(idx)">删</el-button>
          </div>
          <el-button link type="primary" @click="addLine">+ 添加行</el-button>
        </div>
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="emit('update:modelValue', false)">{{ t('production.common.cancel') }}</el-button>
      <el-button type="primary" :loading="saving" @click="handleSubmit">{{ t('production.customers.convertOrder') }}</el-button>
    </template>
  </el-dialog>
</template>
