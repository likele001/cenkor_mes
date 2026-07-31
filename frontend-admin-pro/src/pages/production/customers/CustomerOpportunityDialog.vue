<script setup lang="ts">
import { ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { ElMessage } from 'element-plus'
import type { OpportunityIn } from '@/api/production'

const { t } = useI18n()

const props = defineProps<{
  modelValue: boolean
  editingId: number | null
  form: OpportunityIn & { title: string; stage: string; status: string; is_active: boolean }
  users: { id: number; full_name: string | null; username: string }[]
}>()

const emit = defineEmits<{
  (e: 'update:modelValue', v: boolean): void
  (e: 'save', data: OpportunityIn): void
}>()

const saving = ref(false)
const localForm = ref({ ...props.form })

watch(() => props.form, (v) => { localForm.value = { ...v } }, { deep: true })

function handleSave() {
  const data: OpportunityIn = {
    code: localForm.value.code ? String(localForm.value.code).trim() : null,
    title: String(localForm.value.title || '').trim(),
    stage: String(localForm.value.stage || 'prospecting'),
    status: String(localForm.value.status || 'open'),
    amount: localForm.value.amount === null ? null : Number(localForm.value.amount),
    probability: localForm.value.probability === null ? null : Number(localForm.value.probability),
    expected_close_date: localForm.value.expected_close_date || null,
    owner_user_id: localForm.value.owner_user_id || null,
    is_active: Boolean(localForm.value.is_active),
    remark: localForm.value.remark ? String(localForm.value.remark).trim() : null,
  }
  if (!data.title) {
    ElMessage.error(t('production.customers.pleaseInputOppTitle'))
    return
  }
  saving.value = true
  emit('save', data)
}
</script>

<template>
  <el-dialog
    :model-value="modelValue"
    @update:model-value="emit('update:modelValue', $event)"
    :title="props.editingId ? '编辑销售机会' : '新增销售机会'"
    width="640px"
    destroy-on-close
  >
    <el-form :model="localForm" label-width="100px">
      <el-form-item label="编号"><el-input v-model="localForm.code" placeholder="留空自动生成" /></el-form-item>
      <el-form-item label="标题"><el-input v-model="localForm.title" /></el-form-item>
      <el-form-item label="阶段">
        <el-select v-model="localForm.stage" style="width: 220px">
          <el-option :label="t('production.customers.stageProspecting')" value="prospecting" />
          <el-option :label="t('production.customers.stageQualified')" value="qualified" />
          <el-option :label="t('production.customers.stageQuoted')" value="quoted" />
          <el-option :label="t('production.customers.stageNegotiation')" value="negotiation" />
          <el-option :label="t('production.customers.stageWon')" value="won" />
          <el-option :label="t('production.customers.stageLost')" value="lost" />
        </el-select>
      </el-form-item>
      <el-form-item label="状态">
        <el-select v-model="localForm.status" style="width: 220px">
          <el-option :label="t('production.customers.statusOpen')" value="open" />
          <el-option :label="t('production.customers.stageWon')" value="won" />
          <el-option :label="t('production.customers.stageLost')" value="lost" />
        </el-select>
      </el-form-item>
      <el-form-item label="金额"><el-input-number v-model="localForm.amount" :min="0" :controls="false" style="width: 220px" /></el-form-item>
      <el-form-item label="概率%"><el-input-number v-model="localForm.probability" :min="0" :max="100" :controls="false" style="width: 220px" /></el-form-item>
      <el-form-item label="预计成交"><el-date-picker v-model="localForm.expected_close_date" type="date" value-format="YYYY-MM-DD" style="width: 220px" /></el-form-item>
      <el-form-item label="负责人">
        <el-select v-model="localForm.owner_user_id" clearable filterable placeholder="选择负责人" style="width: 220px">
          <el-option v-for="u in props.users" :key="u.id" :label="u.full_name || u.username" :value="u.id" />
        </el-select>
      </el-form-item>
      <el-form-item :label="t('production.customers.statusEnabled')"><el-switch v-model="localForm.is_active" /></el-form-item>
      <el-form-item :label="t('production.customers.remarkLabel')"><el-input v-model="localForm.remark" type="textarea" :rows="3" /></el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="emit('update:modelValue', false)">{{ t('production.common.cancel') }}</el-button>
      <el-button type="primary" :loading="saving" @click="handleSave">{{ t('production.common.save') }}</el-button>
    </template>
  </el-dialog>
</template>
