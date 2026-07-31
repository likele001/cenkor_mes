<template>
  <view class="ring-wrap">
    <svg :width="size" :height="size" viewBox="0 0 120 120">
      <circle cx="60" cy="60" :r="radius" fill="none" :stroke="bgColor" :stroke-width="strokeWidth" />
      <circle
        cx="60"
        cy="60"
        :r="radius"
        fill="none"
        :stroke="color"
        :stroke-width="strokeWidth"
        stroke-linecap="round"
        :stroke-dasharray="circumference"
        :stroke-dashoffset="dashOffset"
        transform="rotate(-90 60 60)"
      />
      <text x="60" y="60" text-anchor="middle" dominant-baseline="central" :font-size="fontSize" :fill="textColor" font-weight="600">
        {{ displayText }}
      </text>
    </svg>
    <text class="ring-label">{{ label }}</text>
    <text class="ring-sub">{{ sub }}</text>
  </view>
</template>

<script setup lang="ts">
import { computed } from 'vue'

const props = withDefaults(defineProps<{
  percentage: number
  label?: string
  sub?: string
  size?: number
  strokeWidth?: number
  color?: string
  bgColor?: string
  textColor?: string
  fontSize?: number
}>(), {
  percentage: 0,
  label: '',
  sub: '',
  size: 100,
  strokeWidth: 8,
  color: '#10b981',
  bgColor: '#e5e7eb',
  textColor: '#374151',
  fontSize: 22,
})

const radius = 48
const circumference = 2 * Math.PI * radius

const clamped = computed(() => Math.max(0, Math.min(100, props.percentage)))
const dashOffset = computed(() => circumference - (clamped.value / 100) * circumference)
const displayText = computed(() => `${Math.round(clamped.value)}%`)
</script>

<style scoped>
.ring-wrap {
  display: flex;
  flex-direction: column;
  align-items: center;
  width: 140rpx;
}
.ring-label {
  font-size: 22rpx;
  color: #374151;
  text-align: center;
  line-height: 1.3;
  margin-top: 8rpx;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 100%;
}
.ring-sub {
  font-size: 20rpx;
  color: #94a3b8;
}
</style>
