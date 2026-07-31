<template>
  <view class="cust-tabbar">
    <view
      v-for="(item, idx) in tabs"
      :key="item.path"
      class="cust-tabbar-item"
      :class="{ active: current === idx }"
      @tap="switchTab(item.path, idx)"
    >
      <text class="icon">{{ item.icon }}</text>
      <text class="label">{{ t(item.labelKey) }}</text>
    </view>
  </view>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'

const props = defineProps<{ active: number }>()

const { t } = useI18n()
const current = ref(props.active)

watch(
  () => props.active,
  (v) => {
    current.value = v
  },
)

const tabs = [
  { path: '/pages/customer/tab-0/index', icon: '🛒', labelKey: 'customer.nav.order' },
  { path: '/pages/customer/tab-1/index', icon: '📑', labelKey: 'customer.nav.statements' },
  { path: '/pages/customer/tab-2/index', icon: '☺', labelKey: 'customer.nav.profile' },
]

function switchTab(path: string, idx: number) {
  if (current.value === idx) return
  current.value = idx
  uni.reLaunch({ url: path })
}
</script>

<style scoped lang="scss">
.cust-tabbar {
  position: fixed;
  left: 0;
  right: 0;
  bottom: 0;
  display: flex;
  background: #fff;
  border-top: 1rpx solid #e2e8f0;
  padding-bottom: env(safe-area-inset-bottom);
  z-index: 100;
}
.cust-tabbar-item {
  flex: 1;
  text-align: center;
  padding: 16rpx 0 12rpx;
  color: #94a3b8;
}
.cust-tabbar-item.active {
  color: #0284c7;
}
.icon {
  display: block;
  font-size: 36rpx;
}
.label {
  display: block;
  font-size: 22rpx;
  margin-top: 4rpx;
}
</style>
