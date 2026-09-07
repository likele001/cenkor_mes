<!--
  Copyright (C) 2026 CenkorMES Project
  SPDX-License-Identifier: AGPL-3.0
-->
<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { showLoadingToast, showSuccessToast, showToast, closeToast } from 'vant'
import { changePassword, me, updateProfile, type MeOut } from '@/api/auth'
import { getFeishuBindStatus, getFeishuBindUrl } from '@/api/feishu'
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

async function loadMe() {
  loading.value = true
  try {
    meData.value = await me()
    fillForm(meData.value)
    await loadFeishuStatus()
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
