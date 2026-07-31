<template>
  <AdminPage title="个人资料" class="h-full flex flex-col">
    <el-card shadow="never" class="flex-1 flex flex-col overflow-hidden" body-class="flex-1 overflow-hidden !p-0">
<el-form ref="profileRef" :model="profileForm" :rules="profileRules" label-width="88px" v-loading="loading">
        <el-form-item label="账号">
          <el-input :model-value="auth.me?.username" disabled />
        </el-form-item>
        <el-form-item label="姓名" prop="full_name">
          <el-input v-model="profileForm.full_name" placeholder="显示名称" maxlength="128" clearable />
        </el-form-item>
        <el-form-item label="手机号" prop="phone">
          <el-input v-model="profileForm.phone" placeholder="11 位手机号" maxlength="11" clearable />
        </el-form-item>
        <el-form-item label="邮箱" prop="email">
          <el-input v-model="profileForm.email" placeholder="联系邮箱" maxlength="128" clearable />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :loading="profileSaving" @click="onSaveProfile">保存资料</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <el-card class="mt-4">
      <template #header>
        <span class="font-semibold">修改密码</span>
      </template>
      <el-form ref="pwdRef" :model="pwdForm" :rules="pwdRules" label-width="100px">
        <el-form-item label="原密码" prop="old_password">
          <el-input v-model="pwdForm.old_password" type="password" show-password autocomplete="current-password" />
        </el-form-item>
        <el-form-item label="新密码" prop="new_password">
          <el-input v-model="pwdForm.new_password" type="password" show-password autocomplete="new-password" />
        </el-form-item>
        <el-form-item label="确认新密码" prop="confirm_password">
          <el-input v-model="pwdForm.confirm_password" type="password" show-password autocomplete="new-password" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :loading="pwdSaving" @click="onChangePassword">修改密码</el-button>
        </el-form-item>
      </el-form>
    </el-card>
  </AdminPage>
</template>

<script setup lang="ts">
import AdminPage from '@/components/admin/AdminPage.vue'
import { onMounted, reactive, ref } from 'vue'
import type { FormInstance, FormRules } from 'element-plus'
import { ElMessage } from 'element-plus'
import { changePasswordApi, updateProfileApi } from '@/api/auth'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const loading = ref(false)
const profileSaving = ref(false)
const pwdSaving = ref(false)

const profileRef = ref<FormInstance>()
const pwdRef = ref<FormInstance>()

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

const profileRules: FormRules = {
  phone: [
    {
      validator: (_r, v, cb) => {
        const s = String(v || '').trim()
        if (!s || phonePattern.test(s)) cb()
        else cb(new Error('手机号格式不正确'))
      },
      trigger: 'blur',
    },
  ],
  email: [
    {
      validator: (_r, v, cb) => {
        const s = String(v || '').trim()
        if (!s || emailPattern.test(s)) cb()
        else cb(new Error('邮箱格式不正确'))
      },
      trigger: 'blur',
    },
  ],
}

const pwdRules: FormRules = {
  old_password: [{ required: true, message: '请输入原密码', trigger: 'blur' }],
  new_password: [
    { required: true, message: '请输入新密码', trigger: 'blur' },
    { min: 6, message: '至少 6 位', trigger: 'blur' },
  ],
  confirm_password: [
    { required: true, message: '请再次输入新密码', trigger: 'blur' },
    {
      validator: (_r, v, cb) => {
        if (v !== pwdForm.new_password) cb(new Error('两次输入不一致'))
        else cb()
      },
      trigger: 'blur',
    },
  ],
}

function fillProfile() {
  const me = auth.me
  if (!me) return
  profileForm.full_name = me.full_name || ''
  profileForm.phone = me.phone || ''
  profileForm.email = me.email || ''
}

async function onSaveProfile() {
  await profileRef.value?.validate()
  profileSaving.value = true
  try {
    const data = await updateProfileApi({
      full_name: profileForm.full_name.trim() || null,
      phone: profileForm.phone.trim() || null,
      email: profileForm.email.trim() || null,
    })
    auth.me = data
    ElMessage.success('资料已保存')
  } finally {
    profileSaving.value = false
  }
}

async function onChangePassword() {
  await pwdRef.value?.validate()
  pwdSaving.value = true
  try {
    await changePasswordApi({
      old_password: pwdForm.old_password,
      new_password: pwdForm.new_password,
    })
    pwdForm.old_password = ''
    pwdForm.new_password = ''
    pwdForm.confirm_password = ''
    pwdRef.value?.resetFields()
    ElMessage.success('密码已修改')
  } finally {
    pwdSaving.value = false
  }
}

onMounted(async () => {
  loading.value = true
  try {
    if (!auth.me) await auth.fetchMe()
    fillProfile()
  } finally {
    loading.value = false
  }
})
</script>
