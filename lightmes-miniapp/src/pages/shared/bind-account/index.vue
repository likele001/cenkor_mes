<template>
  <view class="emp-page">
    <text class="emp-title">绑定微信账号</text>
    <input v-model="username" class="input" placeholder="用户名" />
    <input v-model="password" class="input" password placeholder="密码" />
    <button class="emp-btn-primary" :loading="loading" @tap="bind">绑定</button>
  </view>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { onLoad } from '@dcloudio/uni-app'
import { bindOpenid } from '@/api/auth'
import { useAuthStore } from '@/stores/auth'
import { afterLoginNavigate } from '@/utils/navigate'

const username = ref('')
const password = ref('')
const openid = ref('')
const loading = ref(false)
const auth = useAuthStore()

onLoad((q) => {
  if (q?.openid) openid.value = String(q.openid)
})

async function bind() {
  loading.value = true
  try {
    const res = await bindOpenid({
      username: username.value.trim(),
      password: password.value,
      openid: openid.value,
    })
    if (res.token) {
      await auth.saveToken(res.token)
      await auth.fetchUser(true)
      afterLoginNavigate()
    }
  } catch (e: unknown) {
    uni.showToast({ title: (e as Error).message || '失败', icon: 'none' })
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.input {
  background: #f1f5f9;
  padding: 24rpx;
  border-radius: 12rpx;
  margin: 24rpx 0;
}
</style>
