<script setup lang="ts">
import { onLaunch } from '@dcloudio/uni-app'
import { useAuthStore } from '@/stores/auth'
import { parseTraceCodeFromLaunch, stashPendingTraceCode } from '@/utils/launchTrace'

onLaunch((options: any) => {
  const auth = useAuthStore()
  if (auth.token) {
    auth.fetchUser().catch(() => {})
  }
  const traceCode = parseTraceCodeFromLaunch(options?.query)
  if (traceCode) {
    stashPendingTraceCode(traceCode)
  }
})
</script>

<template>
  <view />
</template>

<style lang="scss">
@use '@/styles/employee-theme.scss';
@use '@/styles/admin-theme.scss';
@use '@/styles/customer-theme.scss';

page {
  background-color: #f4f6f9;
  font-size: 28rpx;
  color: #1f2937;
}
</style>
