<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { parseTenantFromPath, getStoredTenantCode, setStoredTenantCode, tenantH5Path } from '@/utils/tenant'
import { useRoute, useRouter } from 'vue-router'
import { showToast } from 'vant'
import { login } from '@/api/auth'
import { fetchLoginCaptcha } from '@/api/captcha'
import { useAuthStore } from '@/stores/auth'
import { apiGet } from '@/utils/http'
import { loadRememberPreference, saveRememberPreference } from '@/utils/session-token'

const router = useRouter()
const route = useRoute()
const auth = useAuthStore()

const loading = ref(false)
const rememberMe = ref(loadRememberPreference())
const captchaEnabled = ref(false)
const captchaLoading = ref(false)
const TENANT_STORAGE_KEY = 'cenkormes_h5_tenant_code'

const form = reactive({
  tenant_code: localStorage.getItem(TENANT_STORAGE_KEY) || '',
  username: '',
  password: '',
  captcha_code: '',
})

const captcha = reactive({
  captcha_id: '',
  image_base64: '',
})

async function loadPublicConfig() {
  try {
    const cfg = await apiGet<{ login_captcha_enabled?: boolean }>('/platform/public-config')
    captchaEnabled.value = Boolean(cfg.login_captcha_enabled)
  } catch {
    captchaEnabled.value = false
  }
}

async function refreshCaptcha() {
  if (!captchaEnabled.value) return
  captchaLoading.value = true
  try {
    const res = await fetchLoginCaptcha()
    if (!res.enabled) {
      captchaEnabled.value = false
      return
    }
    captcha.captcha_id = res.captcha_id || ''
    captcha.image_base64 = res.image_base64 || ''
    form.captcha_code = ''
  } finally {
    captchaLoading.value = false
  }
}

onMounted(async () => {
  const code = parseTenantFromPath(route.path) || (route.params.tenantCode as string) || getStoredTenantCode()
  if (code) {
    form.tenant_code = code
    setStoredTenantCode(code)
  }
  await loadPublicConfig()
  await refreshCaptcha()
})

async function onSubmit() {
  if (!form.tenant_code?.trim()) {
    showToast('请输入租户编码')
    return
  }
  if (!form.username || !form.password) {
    showToast('请输入账号和密码')
    return
  }
  if (captchaEnabled.value && !form.captcha_code.trim()) {
    showToast('请输入验证码')
    return
  }
  loading.value = true
  try {
    saveRememberPreference(rememberMe.value)
    const token = await login({
      tenant_code: form.tenant_code.trim(),
      username: form.username.trim(),
      password: form.password,
      remember_me: rememberMe.value,
      captcha_id: captchaEnabled.value ? captcha.captcha_id : undefined,
      captcha_code: captchaEnabled.value ? form.captcha_code.trim() : undefined,
    })
    if (!token) {
      showToast('登录失败')
      return
    }
    localStorage.setItem(TENANT_STORAGE_KEY, form.tenant_code.trim())
    auth.setToken(token, rememberMe.value)
    await auth.fetchMe()
    const raw = (route.query.redirect as string) || (auth.isCustomer ? '/customer/order' : '/home')
    router.replace(tenantH5Path(raw, form.tenant_code.trim()))
  } catch {
    await refreshCaptcha()
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="min-h-dvh bg-zinc-50 px-4 pt-14">
    <div class="mx-auto w-full max-w-sm">
      <div class="mb-6 text-center">
        <div class="text-2xl font-semibold text-zinc-900">辰科MES</div>
        <div class="mt-2 text-sm text-zinc-500">移动端登录</div>
        <a href="https://mes.cenkor.cn" target="_blank" rel="noopener" class="mt-3 inline-block text-xs text-blue-600 underline underline-offset-2">
          了解产品与功能 →
        </a>
      </div>

      <van-cell-group inset>
        <van-field v-model="form.tenant_code" label="租户编码" placeholder="如 DEMO" autocomplete="organization" />
        <van-field v-model="form.username" label="账号" placeholder="请输入账号" autocomplete="username" />
        <van-field
          v-model="form.password"
          label="密码"
          type="password"
          placeholder="请输入密码"
          autocomplete="current-password"
        />
        <van-field v-if="captchaEnabled" v-model="form.captcha_code" label="验证码" placeholder="图中字符" maxlength="6">
          <template #button>
            <img
              v-if="captcha.image_base64"
              :src="`data:image/png;base64,${captcha.image_base64}`"
              class="h-9 w-24 border border-zinc-200 rounded"
              alt="验证码"
              @click="refreshCaptcha"
            />
          </template>
        </van-field>
      </van-cell-group>

      <div class="mx-4 mt-3">
        <van-checkbox v-model="rememberMe" shape="square">记住登录（7 天内免登录）</van-checkbox>
        <p class="text-xs text-zinc-500 mt-2">未勾选：8 小时后自动退出，关闭浏览器也需重新登录</p>
      </div>

      <div class="mt-4">
        <van-button block type="primary" :loading="loading" @click="onSubmit">登录</van-button>
      </div>
    </div>
  </div>
</template>
