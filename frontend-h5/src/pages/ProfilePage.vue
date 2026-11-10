<!--
  Copyright (C) 2026 CenkorMES Project
  SPDX-License-Identifier: AGPL-3.0
-->
<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { showLoadingToast, showSuccessToast, showToast, closeToast } from 'vant'
import { changePassword, me, updateProfile, type MeOut } from '@/api/auth'
import { bindImUser, getBindStatus, getFeishuBindUrl, type BindStatusOut } from '@/api/feishu'
import { useAuthStore } from '@/stores/auth'

const router = useRouter()
const route = useRoute()
const auth = useAuthStore()
const loading = ref(false)
const profileSaving = ref(false)
const pwdSaving = ref(false)
const showPwd = ref(false)

const meData = ref<MeOut | null>(null)
const bindStatus = ref<BindStatusOut | null>(null)
const feishuBinding = ref(false)
const imBinding = ref<'' | 'wecom' | 'dingtalk'>('')
const imForm = reactive({ wecom: '', dingtalk: '' })

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

async function loadBindStatus() {
  try {
    bindStatus.value = await getBindStatus()
    imForm.wecom = bindStatus.value.wecom?.userid || ''
    imForm.dingtalk = bindStatus.value.dingtalk?.userid || ''
  } catch {
    bindStatus.value = null
  }
}

async function loadMe() {
  loading.value = true
  try {
    meData.value = await me()
    fillForm(meData.value)
    await loadBindStatus()
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
    showToast(e instanceof Error ? e.message : '飞书绑定暂不可用')
  } finally {
    feishuBinding.value = false
  }
}

async function onBindIm(channel: 'wecom' | 'dingtalk') {
  const userid = imForm[channel].trim()
  if (!userid) {
    showToast(`请输入${channel === 'wecom' ? '企微' : '钉钉'} UserID`)
    return
  }
  imBinding.value = channel
  try {
    await bindImUser(channel, userid)
    showSuccessToast('绑定成功')
    await loadBindStatus()
  } catch (e: unknown) {
    showToast(e instanceof Error ? e.message : '绑定失败')
  } finally {
    imBinding.value = ''
  }
}

onMounted(async () => {
  if (route.query.feishu_bound === '1') {
    await loadMe()
    showSuccessToast('飞书绑定成功，请打开机器人对话并发送「测试」')
    router.replace({ path: '/profile' })
    return
  }
  await loadMe()
})
</script>

<template>
  <div v-if="loading" class="py-12 text-center text-sm text-zinc-500">加载中...</div>
  <div v-else class="space-y-4">
    <van-cell-group inset title="账号信息">
      <van-field label="账号" :model-value="meData?.username" readonly />
      <van-field v-model="profileForm.full_name" label="姓名" placeholder="显示名称" clearable />
      <van-field v-model="profileForm.phone" label="手机号" type="tel" maxlength="11" placeholder="11 位手机号" clearable />
      <van-field v-model="profileForm.email" label="邮箱" placeholder="联系邮箱" clearable />
    </van-cell-group>
    <div class="px-4">
      <van-button block type="primary" round :loading="profileSaving" @click="onSaveProfile">保存资料</van-button>
    </div>

    <van-cell-group v-if="bindStatus" inset title="消息绑定">
      <van-cell
        title="飞书通知"
        :value="bindStatus.feishu.bound ? '已绑定' : bindStatus.feishu.available ? '未绑定' : '未开通'"
      />
      <div v-if="!bindStatus.feishu.available" class="px-4 pb-3 text-xs text-zinc-400">
        飞书为免费能力，管理员在后台「系统设置 → 飞书」配置 App ID 后即可绑定。
      </div>
      <template v-else-if="!bindStatus.feishu.bound">
        <div class="px-4 pb-3 text-xs text-zinc-400">绑定后派工/报工/工资等通知会推送到飞书机器人单聊</div>
        <div class="px-4 pb-3">
          <van-button block type="primary" plain round :loading="feishuBinding" @click="onBindFeishu">
            绑定飞书
          </van-button>
        </div>
      </template>
      <div v-else class="px-4 pb-3 text-xs text-zinc-400">绑定时间：{{ bindStatus.feishu.bound_at || '—' }}</div>

      <van-cell
        title="企业微信"
        :value="!bindStatus.wecom.available ? '未开通' : bindStatus.wecom.bound ? '已绑定' : '未绑定'"
      />
      <template v-if="bindStatus.wecom.available">
        <van-field v-model="imForm.wecom" label="UserID" placeholder="企业微信成员账号" clearable />
        <div class="px-4 pb-3">
          <van-button block type="primary" plain round :loading="imBinding === 'wecom'" @click="onBindIm('wecom')">
            {{ bindStatus.wecom.bound ? '更新企微绑定' : '绑定企业微信' }}
          </van-button>
        </div>
      </template>
      <div v-else class="px-4 pb-3 text-xs text-zinc-400">
        「企微/钉钉通知」为付费扩展，请在应用市场的扩展应用中开通后再绑定。
      </div>

      <van-cell
        title="钉钉"
        :value="!bindStatus.dingtalk.available ? '未开通' : bindStatus.dingtalk.bound ? '已绑定' : '未绑定'"
      />
      <template v-if="bindStatus.dingtalk.available">
        <van-field v-model="imForm.dingtalk" label="UserID" placeholder="钉钉成员账号" clearable />
        <div class="px-4 pb-3">
          <van-button block type="primary" plain round :loading="imBinding === 'dingtalk'" @click="onBindIm('dingtalk')">
            {{ bindStatus.dingtalk.bound ? '更新钉钉绑定' : '绑定钉钉' }}
          </van-button>
        </div>
      </template>
      <div v-else class="px-4 pb-3 text-xs text-zinc-400">
        钉钉通知复用「企微/钉钉通知」付费扩展，开通后即可在此自助绑定。
      </div>
    </van-cell-group>

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
