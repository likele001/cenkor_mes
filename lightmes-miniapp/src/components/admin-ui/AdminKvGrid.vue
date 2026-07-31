<template>
  <view class="adm-kv-grid">
    <view v-for="row in rows" :key="row.label" class="adm-kv-row">
      <text class="adm-kv-k">{{ row.label }}</text>
      <text class="adm-kv-v">{{ row.value || '—' }}</text>
    </view>
  </view>
</template>

<script setup lang="ts">
export type KvRow = { label: string; value?: string | number | null }

defineProps<{
  rows: KvRow[]
}>()
</script>
