<template>
  <view
    class="login-page"
  >
    <view class="brand">
      <text class="logo">CenkorMES</text>
      <text class="sub">员工移动工作台</text>
    </view>

    <view v-if="mode === 'select'" class="card">
      <text class="portal-tip">使用员工/班组长账号登录，进入报工、任务、考勤、工资</text>
      <button class="btn-primary wx" :loading="loading" @tap="handleWxLogin">微信一键登录</button>
      <text class="wx-hint">与 PC 管理后台、H5 为同一套用户名；微信绑定后下次可一键进入</text>
      <button class="link-btn" @tap="mode = 'account'">账号密码登录</button>
    </view>

    <view v-else-if="mode === 'account'" class="card">
      <text class="portal-tip">使用员工/班组长账号登录，进入报工、任务、考勤、工资</text>
      <input v-model="username" class="input" placeholder="用户名" />
      <input v-model="password" class="input" password placeholder="密码" />
      <view v-if="captchaEnabled" class="captcha-row">
        <input v-model="captchaCode" class="input captcha-input" placeholder="验证码" maxlength="6" />
        <image
          v-if="captchaImage"
          class="captcha-img"
          :src="`data:image/png;base64,${captchaImage}`"
          mode="aspectFit"
          @tap="refreshCaptcha"
        />
        <view v-else class="captcha-placeholder" @tap="refreshCaptcha">加载验证码</view>
      </view>
      <button class="btn-primary" :loading="loading" @tap="handleAccountLogin">登录员工端</button>
      <button class="link-btn" @tap="mode = 'select'">返回</button>
    </view>

    <view v-else class="card">
      <text class="hint">首次使用请绑定本企业已有账号（与 PC、H5 同一用户名）</text>
      <input v-model="bindUsername" class="input" placeholder="用户名" />
      <input v-model="bindPassword" class="input" password placeholder="密码" />
      <button class="btn-primary" :loading="loading" @tap="handleBind">绑定并进入员工端</button>
    </view>

    <view class="trace-link" @tap="goTrace">
      <text>产品溯源查询（无需登录）</text>
    </view>
  </view>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import { onShow } from '@dcloudio/uni-app'
import { bindOpenid, loginWithPassword, miniappLogin } from '@/api/auth'
import { fetchLoginCaptcha } from '@/api/captcha'
import { useAuthStore } from '@/stores/auth'
import { consumePendingTraceCode, navigateToTracePage } from '@/utils/launchTrace'
import { afterLoginNavigate } from '@/utils/navigate'

const auth = useAuthStore()
const mode = ref<'select' | 'account' | 'bind'>('select')
const loading = ref(false)
const captchaEnabled = ref(false)
const username = ref('')
const password = ref('')
const captchaCode = ref('')
const captchaId = ref('')
const captchaImage = ref('')
const bindUsername = ref('')
const bindPassword = ref('')
const openid = ref('')

watch(mode, (v) => {
  if (v === 'account') refreshCaptcha()
})

onShow(() => {
  if (mode.value === 'account') refreshCaptcha()

  const pendingTrace = consumePendingTraceCode()
  if (pendingTrace) {
    navigateToTracePage(pendingTrace)
  }
})

async function refreshCaptcha() {
  try {
    const res = await fetchLoginCaptcha()
    captchaEnabled.value = Boolean(res.enabled)
    if (!res.enabled) {
      captchaId.value = ''
      captchaImage.value = ''
      captchaCode.value = ''
      return
    }
    captchaId.value = res.captcha_id || ''
    captchaImage.value = res.image_base64 || ''
    captchaCode.value = ''
  } catch {
    captchaEnabled.value = false
  }
}

function finishLogin() {
  afterLoginNavigate()
}

function goTrace() {
  uni.navigateTo({ url: '/pages/shared/trace/index' })
}

async function handleWxLogin() {
  loading.value = true
  try {
    const { code } = await uni.login({ provider: 'weixin' })
    const res = await miniappLogin(code)
    if (res.need_bind) {
      openid.value = res.openid || ''
      mode.value = 'bind'
      return
    }
    const token = res.token
    if (token) {
      await auth.saveToken(token)
      await auth.fetchUser()
      finishLogin()
    }
  } catch (e: unknown) {
    uni.showToast({ title: (e as Error).message || '登录失败', icon: 'none' })
  } finally {
    loading.value = false
  }
}

async function handleAccountLogin() {
  if (!username.value || !password.value) {
    uni.showToast({ title: '请填写完整', icon: 'none' })
    return
  }
  if (captchaEnabled.value && !captchaCode.value.trim()) {
    uni.showToast({ title: '请输入验证码', icon: 'none' })
    return
  }
  loading.value = true
  try {
    const data = await loginWithPassword({
      username: username.value.trim(),
      password: password.value,
      remember_me: true,
      captcha_id: captchaEnabled.value ? captchaId.value : undefined,
      captcha_code: captchaEnabled.value ? captchaCode.value.trim() : undefined,
    })
    const token = data.token || data.access_token
    if (token) {
      await auth.saveToken(token)
      await auth.fetchUser()
      finishLogin()
    }
  } catch {
    await refreshCaptcha()
  } finally {
    loading.value = false
  }
}

async function handleBind() {
  if (!bindUsername.value || !bindPassword.value) {
    uni.showToast({ title: '请填写用户名和密码', icon: 'none' })
    return
  }
  loading.value = true
  try {
    const res = await bindOpenid({
      username: bindUsername.value.trim(),
      password: bindPassword.value,
      openid: openid.value,
    })
    if (res.token) {
      await auth.saveToken(res.token)
      await auth.fetchUser()
      finishLogin()
    }
  } catch (e: unknown) {
    uni.showToast({ title: (e as Error).message || '绑定失败', icon: 'none' })
  } finally {
    loading.value = false
  }
}
</script>

<style scoped lang="scss">
.login-page {
  min-height: 100vh;
  padding: 80rpx 40rpx 40rpx;
  background: linear-gradient(180deg, #eff6ff, #f8fafc);
}
.login-admin {
  background: linear-gradient(180deg, #eef2ff, #f8fafc);
}
.login-customer {
  background: linear-gradient(180deg, #e0f2fe, #f8fafc);
}
.brand {
  text-align: center;
  margin-bottom: 24rpx;
}
.logo {
  font-size: 56rpx;
  font-weight: 800;
  color: #1d4ed8;
}
.login-admin .logo {
  color: #4338ca;
}
.login-customer .logo {
  color: #0369a1;
}
.sub {
  display: block;
  margin-top: 12rpx;
  color: #64748b;
}
.lang-row {
  text-align: right;
  font-size: 24rpx;
  color: #0284c7;
  margin-bottom: 16rpx;
}
.portal-tabs {
  display: flex;
  background: #fff;
  border-radius: 16rpx;
  padding: 8rpx;
  margin-bottom: 24rpx;
}
.portal-tab {
  flex: 1;
  text-align: center;
  padding: 18rpx 0;
  border-radius: 12rpx;
  color: #64748b;
  font-size: 26rpx;
}
.portal-tab.active {
  background: #2563eb;
  color: #fff;
  font-weight: 600;
}
.login-admin .portal-tab.active {
  background: #4338ca;
}
.login-customer .portal-tab.active {
  background: #0284c7;
}
.card {
  background: #fff;
  border-radius: 24rpx;
  padding: 40rpx;
}
.portal-tip {
  display: block;
  font-size: 24rpx;
  color: #64748b;
  margin-bottom: 24rpx;
  line-height: 1.5;
}
.input {
  background: #f1f5f9;
  border-radius: 12rpx;
  padding: 24rpx;
  margin-bottom: 24rpx;
}
.captcha-row {
  display: flex;
  align-items: center;
  gap: 16rpx;
  margin-bottom: 24rpx;
}
.captcha-input {
  flex: 1;
  margin-bottom: 0;
}
.captcha-img,
.captcha-placeholder {
  width: 200rpx;
  height: 80rpx;
  border-radius: 12rpx;
  background: #e2e8f0;
  flex-shrink: 0;
}
.captcha-placeholder {
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 22rpx;
  color: #64748b;
}
.btn-primary {
  background: linear-gradient(135deg, #3b82f6, #1d4ed8);
  color: #fff;
  border-radius: 12rpx;
}
.login-admin .btn-primary {
  background: linear-gradient(135deg, #6366f1, #4338ca);
}
.login-customer .btn-primary {
  background: linear-gradient(135deg, #38bdf8, #0284c7);
}
.wx {
  margin-bottom: 24rpx;
}
.link-btn {
  background: transparent;
  color: #2563eb;
  font-size: 28rpx;
  margin-top: 16rpx;
}
.link-btn::after {
  border: none;
}
.wx-hint {
  display: block;
  font-size: 22rpx;
  color: #64748b;
  text-align: center;
  margin: 16rpx 0;
}
.hint {
  display: block;
  margin-bottom: 24rpx;
  color: #64748b;
  font-size: 26rpx;
}
.trace-link {
  margin-top: 32rpx;
  text-align: center;
  color: #0284c7;
  font-size: 26rpx;
}
</style>
