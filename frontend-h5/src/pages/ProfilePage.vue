<script setup lang="ts">
import { onMounted, reactive, ref, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { showLoadingToast, showSuccessToast, showToast, closeToast } from 'vant'
import { changePassword, me, updateProfile, type MeOut } from '@/api/auth'
import { getFeishuBindStatus, getFeishuBindUrl } from '@/api/feishu'
import { getWecomBindStatus, getWecomBindUrl } from '@/api/wecom'
import { getDingtalkBindStatus, getDingtalkBindUrl } from '@/api/dingtalk'
import { useAuthStore } from '@/stores/auth'

const router = useRouter()
const route = useRoute()
const auth = useAuthStore()
const loading = ref(false)
const profileSaving = ref(false)
const pwdSaving = ref(false)
const showPwd = ref(false)

const meData = ref<MeOut | null>(null)
const feishuEnabled = ref(false)
const feishuBound = ref(false)
const feishuBinding = ref(false)
const feishuBotLink = ref('')
const wecomEnabled = ref(false)
const wecomBound = ref(false)
const wecomUserid = ref('')
const wecomBinding = ref(false)
const dingtalkEnabled = ref(false)
const dingtalkBound = ref(false)
const dingtalkUserid = ref('')
const dingtalkBinding = ref(false)
const showBindQr = ref(false)
const bindAuthorizeUrl = ref('')

const isWecomBrowser = computed(() => /wxwork/i.test(navigator.userAgent || ''))

const bindQrImageUrl = computed(() => {
  if (!bindAuthorizeUrl.value) return ''
  return `https://api.qrserver.com/v1/create-qr-code/?size=240x240&data=${encodeURIComponent(bindAuthorizeUrl.value)}`
})

const profileForm = reactive({
  full_name: '',
  phone: '',
  email: '',
})

const pwdForm = reactive({
  old_password: '',
  new_password: '',
  confirm_password: '',
})

const phonePattern = /^1[3-9]\d{9}$/
const emailPattern = /^[^@\s]+@[^@\s]+\.[^@\s]+$/

const canAi = computed(() => auth.hasPermission('ai.use'))

function go(path: string) {
  router.push(path)
}

function fillForm(data: MeOut) {
  profileForm.full_name = data.full_name || ''
  profileForm.phone = data.phone || ''
  profileForm.email = data.email || ''
}

function validateProfile(): boolean {
  const phone = profileForm.phone.trim()
  const email = profileForm.email.trim()
  if (phone && !phonePattern.test(phone)) {
    showToast('手机号格式不正确')
    return false
  }
  if (email && !emailPattern.test(email)) {
    showToast('邮箱格式不正确')
    return false
  }
  return true
}

async function loadFeishuStatus() {
  try {
    const fs = await getFeishuBindStatus()
    feishuEnabled.value = fs.enabled
    feishuBound.value = fs.bound
    feishuBotLink.value = fs.bot_open_link || ''
  } catch {
    feishuEnabled.value = false
    feishuBound.value = false
    feishuBotLink.value = ''
  }
}

async function loadDingtalkStatus() {
  try {
    const ds = await getDingtalkBindStatus()
    dingtalkEnabled.value = ds.enabled
    dingtalkBound.value = ds.bound
    dingtalkUserid.value = ds.dingtalk_userid || ''
  } catch {
    dingtalkEnabled.value = false
    dingtalkBound.value = false
    dingtalkUserid.value = ''
  }
}

async function loadWecomStatus() {
  try {
    const ws = await getWecomBindStatus()
    wecomEnabled.value = ws.enabled
    wecomBound.value = ws.bound
    wecomUserid.value = ws.wecom_userid || ''
  } catch {
    wecomEnabled.value = false
    wecomBound.value = false
    wecomUserid.value = ''
  }
}

async function loadMe() {
  loading.value = true
  try {
    meData.value = await me()
    fillForm(meData.value)
    await loadFeishuStatus()
    await loadWecomStatus()
    await loadDingtalkStatus()
    auth.userInfo = {
      full_name: meData.value.full_name,
      roles: meData.value.roles,
      username: meData.value.username,
      phone: meData.value.phone,
      email: meData.value.email,
    }
  } finally {
    loading.value = false
  }
}

async function onSaveProfile() {
  if (!validateProfile()) return
  profileSaving.value = true
  showLoadingToast({ message: '保存中...', duration: 0 })
  try {
    const data = await updateProfile({
      full_name: profileForm.full_name.trim() || null,
      phone: profileForm.phone.trim() || null,
      email: profileForm.email.trim() || null,
    })
    meData.value = data
    auth.userInfo = {
      full_name: data.full_name,
      roles: data.roles,
      username: data.username,
      phone: data.phone,
      email: data.email,
    }
    auth.permissions = data.permissions || []
    showSuccessToast('资料已保存')
  } finally {
    profileSaving.value = false
    closeToast()
  }
}

async function onChangePassword() {
  if (!pwdForm.old_password) {
    showToast('请输入原密码')
    return
  }
  if (pwdForm.new_password.length < 6) {
    showToast('新密码至少 6 位')
    return
  }
  if (pwdForm.new_password !== pwdForm.confirm_password) {
    showToast('两次新密码不一致')
    return
  }
  pwdSaving.value = true
  showLoadingToast({ message: '提交中...', duration: 0 })
  try {
    await changePassword({
      old_password: pwdForm.old_password,
      new_password: pwdForm.new_password,
    })
    pwdForm.old_password = ''
    pwdForm.new_password = ''
    pwdForm.confirm_password = ''
    showPwd.value = false
    showSuccessToast('密码已修改')
  } finally {
    pwdSaving.value = false
    closeToast()
  }
}

async function onBindFeishu() {
  feishuBinding.value = true
  try {
    const res = await getFeishuBindUrl()
    window.location.href = res.authorize_url
  } catch (e: unknown) {
    showToast(String(e))
  } finally {
    feishuBinding.value = false
  }
}

async function onOpenFeishuBot() {
  if (!feishuBotLink.value) {
    showToast('请先在管理后台配置飞书 App ID')
    return
  }
  window.location.href = feishuBotLink.value
}

async function onBindDingtalk() {
  dingtalkBinding.value = true
  try {
    const res = await getDingtalkBindUrl()
    window.location.href = res.authorize_url
  } catch (e: unknown) {
    showToast(String(e))
  } finally {
    dingtalkBinding.value = false
  }
}

async function onBindWecom() {
  wecomBinding.value = true
  try {
    const res = await getWecomBindUrl()
    if (isWecomBrowser.value) {
      window.location.href = res.authorize_url
      return
    }
    bindAuthorizeUrl.value = res.authorize_url
    showBindQr.value = true
  } catch (e: unknown) {
    showToast(String(e))
  } finally {
    wecomBinding.value = false
  }
}

async function copyBindLink() {
  if (!bindAuthorizeUrl.value) return
  try {
    await navigator.clipboard.writeText(bindAuthorizeUrl.value)
    showSuccessToast('链接已复制，请在手机企业微信中打开')
  } catch {
    showToast('复制失败，请长按二维码识别')
  }
}

onMounted(async () => {
  if (route.query.feishu_bound === '1') {
    await loadMe()
    showSuccessToast('飞书绑定成功，请打开机器人对话并发送「测试」')
    router.replace({ path: '/profile' })
    return
  }
  if (route.query.wecom_bound === '1') {
    await loadMe()
    showSuccessToast('企业微信绑定成功，派工/报工通知将推送到应用消息')
    router.replace({ path: '/profile' })
    return
  }
  if (route.query.dingtalk_bound === '1') {
    await loadMe()
    showSuccessToast('钉钉绑定成功，派工/报工通知将推送到工作通知')
    router.replace({ path: '/profile' })
    return
  }
  await loadMe()
})
</script>

<template>
  <div v-if="loading" class="py-12 text-center text-sm text-zinc-500">加载中...</div>
  <div v-else class="space-y-4">
    <van-cell-group inset title="AI 助手">
      <van-cell title="智能帮助" is-link @click="go('/help')" />
      <van-cell v-if="canAi" title="工厂助手" is-link @click="go('/ai-assistant')" />
    </van-cell-group>

    <van-cell-group inset title="账号信息">
      <van-field label="账号" :model-value="meData?.username" readonly />
      <van-field v-model="profileForm.full_name" label="姓名" placeholder="显示名称" clearable />
      <van-field v-model="profileForm.phone" label="手机号" type="tel" maxlength="11" placeholder="11 位手机号" clearable />
      <van-field v-model="profileForm.email" label="邮箱" placeholder="联系邮箱" clearable />
    </van-cell-group>
    <div class="px-4">
      <van-button block type="primary" round :loading="profileSaving" @click="onSaveProfile">保存资料</van-button>
    </div>

    <van-cell-group v-if="feishuEnabled" inset title="飞书通知">
      <van-cell title="绑定状态" :value="feishuBound ? '已绑定' : '未绑定'" />
      <van-cell v-if="!feishuBound" title="说明" label="绑定后派工/报工/工资等通知会推送到飞书机器人单聊" />
      <div v-if="!feishuBound" class="px-4 pb-4">
        <van-button block type="primary" plain round :loading="feishuBinding" @click="onBindFeishu">
          绑定飞书
        </van-button>
      </div>
      <div v-else class="px-4 pb-4">
        <van-button block type="primary" plain round @click="onOpenFeishuBot">打开飞书机器人</van-button>
      </div>
    </van-cell-group>

    <van-cell-group v-if="dingtalkEnabled" inset title="钉钉通知">
      <van-cell title="绑定状态" :value="dingtalkBound ? '已绑定' : '未绑定'" />
      <van-cell v-if="dingtalkBound && dingtalkUserid" title="钉钉账号" :value="dingtalkUserid" />
      <div v-if="!dingtalkBound" class="px-4 pb-4">
        <van-button block type="primary" plain round :loading="dingtalkBinding" @click="onBindDingtalk">
          绑定钉钉
        </van-button>
      </div>
    </van-cell-group>

    <van-cell-group v-if="wecomEnabled" inset title="企业微信通知">
      <van-cell title="绑定状态" :value="wecomBound ? '已绑定' : '未绑定'" />
      <van-cell v-if="wecomBound && wecomUserid" title="企微账号" :value="wecomUserid" />
      <van-cell
        v-if="!wecomBound"
        title="绑定说明"
        :label="isWecomBrowser
          ? '当前已在企业微信内，可直接点击下方按钮授权绑定'
          : '电脑浏览器无法直接绑定。请用手机企业微信扫码，或让管理员在后台按手机号批量匹配'"
      />
      <div v-if="!wecomBound" class="px-4 pb-4 space-y-2">
        <van-button block type="primary" plain round :loading="wecomBinding" @click="onBindWecom">
          {{ isWecomBrowser ? '绑定企业微信' : '扫码绑定（手机企业微信）' }}
        </van-button>
      </div>
    </van-cell-group>

    <van-popup v-model:show="showBindQr" round closeable position="bottom" :style="{ padding: '20px 16px 28px' }">
      <div class="text-center">
        <div class="text-base font-semibold mb-2">手机企业微信扫码绑定</div>
        <p class="text-xs text-zinc-500 mb-4 leading-relaxed">
          1. 打开手机「企业微信」→ 扫一扫<br />
          2. 扫描下方二维码并确认授权<br />
          3. 完成后回到本页刷新，应显示「已绑定」
        </p>
        <img
          v-if="bindQrImageUrl"
          :src="bindQrImageUrl"
          alt="企业微信绑定二维码"
          class="mx-auto w-[240px] h-[240px] border border-zinc-200 rounded-lg"
        />
        <van-button class="mt-4" size="small" plain type="primary" @click="copyBindLink">复制链接到手机打开</van-button>
        <p class="text-xs text-zinc-400 mt-3">也可让管理员在 PC 后台 → 企业微信推送 → 用户绑定 → 批量匹配手机号</p>
      </div>
    </van-popup>

    <van-cell-group inset title="修改密码">
      <van-cell title="修改登录密码" is-link :value="showPwd ? '收起' : '展开'" @click="showPwd = !showPwd" />
      <template v-if="showPwd">
        <van-field v-model="pwdForm.old_password" label="原密码" type="password" placeholder="请输入原密码" />
        <van-field v-model="pwdForm.new_password" label="新密码" type="password" placeholder="至少 6 位" />
        <van-field v-model="pwdForm.confirm_password" label="确认密码" type="password" placeholder="再次输入新密码" />
      </template>
    </van-cell-group>
    <div v-if="showPwd" class="px-4">
      <van-button block type="primary" plain round :loading="pwdSaving" @click="onChangePassword">确认修改密码</van-button>
    </div>
  </div>
</template>
