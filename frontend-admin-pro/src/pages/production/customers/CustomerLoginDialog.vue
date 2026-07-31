<script setup lang="ts">
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { ElMessage } from 'element-plus'

const { t } = useI18n()

const props = defineProps<{
  modelValue: boolean
  hasExistingLogin: boolean
  loginUsername: string
}>()

const emit = defineEmits<{
  (e: 'update:modelValue', v: boolean): void
  (e: 'save', payload: { login_username: string; login_password?: string }): void
}>()

const saving = ref(false)
const loginUsername = ref(props.loginUsername)
const loginPassword = ref('')

function handleSave() {
  if (!loginUsername.value.trim()) {
    ElMessage.warning(t('production.customers.pleaseInputLoginAccount'))
    return
  }
  if (!props.hasExistingLogin && (!loginPassword.value || loginPassword.value.length < 6)) {
    ElMessage.warning(t('production.customers.passwordMinLength'))
    return
  }
  saving.value = true
  emit('save', {
    login_username: loginUsername.value.trim(),
    login_password: loginPassword.value || undefined,
  })
}
</script>

<template>
  <el-dialog
    :model-value="modelValue"
    @update:model-value="emit('update:modelValue', $event)"
    title="客户 H5 登录账号"
    width="480px"
    destroy-on-close
  >
    <el-form label-width="90px">
      <el-form-item :label="t('production.customers.loginAccount')" required>
        <el-input v-model="loginUsername" placeholder="H5 登录用户名" />
      </el-form-item>
      <el-form-item :label="props.hasExistingLogin ? t('production.customers.resetPassword') : t('production.customers.loginPassword')">
        <el-input v-model="loginPassword" type="password" show-password :placeholder="t('production.customers.passwordNewPlaceholder')" />
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="emit('update:modelValue', false)">{{ t('production.common.cancel') }}</el-button>
      <el-button type="primary" :loading="saving" @click="handleSave">{{ t('production.common.save') }}</el-button>
    </template>
  </el-dialog>
</template>
