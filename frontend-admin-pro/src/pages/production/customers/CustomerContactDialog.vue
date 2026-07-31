<script setup lang="ts">
import { ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { ElMessage } from 'element-plus'
import type { CustomerContactIn, CustomerContactOut } from '@/api/production'

const { t } = useI18n()

const props = defineProps<{
  modelValue: boolean
  editingId: number | null
  form: CustomerContactIn & { name: string; is_primary: boolean; is_active: boolean }
}>()

const emit = defineEmits<{
  (e: 'update:modelValue', v: boolean): void
  (e: 'save', data: CustomerContactIn): void
}>()

const saving = ref(false)
const localForm = ref({ ...props.form })

watch(() => props.form, (v) => { localForm.value = { ...v } }, { deep: true })

function handleSave() {
  const data: CustomerContactIn = {
    name: String(localForm.value.name || '').trim(),
    phone: localForm.value.phone ? String(localForm.value.phone).trim() : null,
    email: localForm.value.email ? String(localForm.value.email).trim() : null,
    title: localForm.value.title ? String(localForm.value.title).trim() : null,
    is_primary: Boolean(localForm.value.is_primary),
    is_active: Boolean(localForm.value.is_active),
    remark: localForm.value.remark ? String(localForm.value.remark).trim() : null,
  }
  if (!data.name) {
    ElMessage.error(t('production.customers.pleaseInputContactName'))
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
    :title="props.editingId ? '编辑联系人' : '新增联系人'"
    width="520px"
    destroy-on-close
  >
    <el-form :model="localForm" label-width="90px">
      <el-form-item :label="t('production.customers.name')"><el-input v-model="localForm.name" /></el-form-item>
      <el-form-item :label="t('production.customers.phoneLabel')"><el-input v-model="localForm.phone" /></el-form-item>
      <el-form-item label="邮箱"><el-input v-model="localForm.email" /></el-form-item>
      <el-form-item label="职位"><el-input v-model="localForm.title" /></el-form-item>
      <el-form-item label="主联系人"><el-switch v-model="localForm.is_primary" /></el-form-item>
      <el-form-item :label="t('production.customers.statusEnabled')"><el-switch v-model="localForm.is_active" /></el-form-item>
      <el-form-item :label="t('production.customers.remarkLabel')"><el-input v-model="localForm.remark" type="textarea" :rows="3" /></el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="emit('update:modelValue', false)">{{ t('production.common.cancel') }}</el-button>
      <el-button type="primary" :loading="saving" @click="handleSave">{{ t('production.common.save') }}</el-button>
    </template>
  </el-dialog>
</template>
