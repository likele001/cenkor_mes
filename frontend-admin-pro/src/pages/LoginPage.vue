<template>
  <div class="admin-login-page min-h-screen w-screen flex items-center justify-center p-4">
    <div class="absolute inset-0 pointer-events-none overflow-hidden opacity-60" aria-hidden="true">
      <div class="absolute -top-24 -right-24 w-72 h-72 rounded-full admin-login-blob-primary" />
      <div class="absolute -bottom-20 -left-16 w-64 h-64 rounded-full admin-login-blob-secondary" />
    </div>

    <div
      class="admin-login-card relative w-full max-w-[420px] rounded-lg border p-8 sm:p-9 shadow-[var(--el-box-shadow)] admin-interactive"
    >
      <AdminBrand subtitle="CenkorMES" :use-tenant="false" class="mb-1" />
      <p class="text-[13px] text-[var(--admin-brand-subtitle)] mt-4 mb-5">{{ t('auth.login.hint') }}</p>

      <el-form :model="form" :rules="rules" ref="formRef" label-position="top" class="login-form">
        <el-form-item :label="t('auth.login.username')" prop="username">
          <el-input v-model="form.username" autocomplete="off" />
        </el-form-item>
        <el-form-item :label="t('auth.login.password')" prop="password">
          <el-input v-model="form.password" type="password" show-password autocomplete="off" />
        </el-form-item>
        <LoginCaptchaField ref="captchaRef" />
        <el-form-item class="!mb-2">
          <el-checkbox v-model="rememberMe">{{ t('auth.login.rememberMe') }}</el-checkbox>
          <p class="text-xs text-el-placeholder mt-1 w-full">{{ t('auth.login.rememberMeDesc') }}</p>
        </el-form-item>
        <el-form-item class="!mb-0 mt-1">
          <el-button class="w-full" type="primary" :loading="loading" @click="onSubmit">{{ t('auth.login.loginBtn') }}</el-button>
        </el-form-item>
      </el-form>
    </div>
  </div>
</template>

<script setup lang="ts">
import { reactive, ref } from 'vue'
import type { FormInstance, FormRules } from 'element-plus'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { ElMessage } from 'element-plus'
import { useAuthStore } from '@/stores/auth'
import LoginCaptchaField from '@/components/LoginCaptchaField.vue'
import AdminBrand from '@/components/AdminBrand.vue'
import { loadRememberPreference, saveRememberPreference } from '@/utils/session-token'

const router = useRouter()
const route = useRoute()
const auth = useAuthStore()
const { t } = useI18n()

const formRef = ref<FormInstance>()
const loading = ref(false)
const captchaRef = ref<InstanceType<typeof LoginCaptchaField> | null>(null)
const rememberMe = ref(loadRememberPreference())
const form = reactive({ username: '', password: '' })

const rules: FormRules = {
  username: [{ required: true, message: t('auth.login.pleaseEnterUsername'), trigger: 'blur' }],
  password: [{ required: true, message: t('auth.login.pleaseEnterPassword'), trigger: 'blur' }],
}

async function onSubmit() {
  const ok = await formRef.value?.validate().catch(() => false)
  if (!ok) return
  loading.value = true
  try {
    const cap = captchaRef.value
    if (cap && !cap.validate()) {
      ElMessage.warning(t('auth.login.pleaseEnterCaptcha'))
      return
    }
    saveRememberPreference(rememberMe.value)
    await auth.login({ ...form, remember_me: rememberMe.value, ...(cap?.payloadFields() || {}) })
    const redirect =
      typeof route.query.redirect === 'string' ? route.query.redirect : null
    await router.replace(redirect || '/home')
  } catch {
    await captchaRef.value?.refresh()
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.login-form :deep(.el-form-item__label) {
  font-weight: 500;
  color: var(--el-text-color-regular);
}
</style>
