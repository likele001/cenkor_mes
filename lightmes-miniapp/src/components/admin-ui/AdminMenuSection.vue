<template>
  <view v-if="items.length" class="adm-section">
    <view v-if="title" class="adm-section-head">
      <text class="adm-section-title">{{ title }}</text>
      <text v-if="subtitle" class="adm-section-sub">{{ subtitle }}</text>
    </view>
    <view class="adm-menu-grid" :class="{ compact }">
      <view
        v-for="item in items"
        :key="item.path"
        class="adm-menu-item"
        hover-class="adm-menu-item-hover"
        @tap="onTap(item.path)"
      >
        <view class="adm-menu-icon" :class="item.tone || 'blue'">{{ item.icon }}</view>
        <text class="adm-menu-text">{{ item.title }}</text>
      </view>
    </view>
  </view>
</template>

<script setup lang="ts">
import type { AdminMenuItem } from '@/constants/adminMenu'

defineProps<{
  title?: string
  subtitle?: string
  items: AdminMenuItem[]
  compact?: boolean
}>()

const emit = defineEmits<{ navigate: [string] }>()

function onTap(path: string) {
  emit('navigate', path)
}
</script>
