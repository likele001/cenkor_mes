<template>
  <view class="page">
    <view class="tabs">
      <view :class="['tab', tab === 'batch' && 'active']" @tap="tab = 'batch'">批量设置</view>
      <view :class="['tab', tab === 'list' && 'active']" @tap="tab = 'list'">工价列表</view>
    </view>
    <AdminProcessPriceBatchPage v-if="tab === 'batch'" />
    <AdminCrudPage v-else schema-key="processPrices" />
  </view>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import AdminCrudPage from '@/components/admin-ui/AdminCrudPage.vue'
import AdminProcessPriceBatchPage from '@/components/admin-ui/AdminProcessPriceBatchPage.vue'

const tab = ref<'batch' | 'list'>('batch')
</script>

<style scoped>
.tabs {
  display: flex;
  gap: 16rpx;
  margin-bottom: 20rpx;
}
.tab {
  flex: 1;
  text-align: center;
  padding: 16rpx;
  background: #e2e8f0;
  border-radius: 12rpx;
  font-size: 26rpx;
}
.tab.active {
  background: #2563eb;
  color: #fff;
}
.page {
  padding: 20rpx;
}
</style>
