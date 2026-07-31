<template>
  <view class="adm-list-wrap">
    <view v-if="loading" class="adm-empty-tip">加载中...</view>
    <view v-else-if="!items.length" class="adm-empty-tip">{{ emptyText }}</view>
    <view v-else class="adm-list-stack">
      <view
        v-for="(item, idx) in items"
        :key="listKey(item, idx)"
        class="adm-list-card"
        :class="{ 'adm-list-card--actions': hasActions }"
      >
        <view
          class="adm-list-inner"
          :hover-class="bodyTapable ? 'adm-list-card-hover' : ''"
          @tap="onBodyTap(item, idx)"
        >
          <view class="adm-list-body">
            <slot name="item" :item="item" :index="idx" />
          </view>
          <view v-if="showChevron && bodyTapable" class="adm-list-chevron" aria-hidden="true">
            <text>›</text>
          </view>
        </view>
        <view v-if="hasActions" class="adm-card-btns-wrap" @tap.stop>
          <slot name="actions" :item="item" :index="idx" />
        </view>
      </view>
    </view>
  </view>
</template>

<script setup lang="ts">
import { computed, useSlots } from 'vue'

const props = withDefaults(
  defineProps<{
    items: unknown[]
    loading?: boolean
    emptyText?: string
    /** 是否显示右侧箭头（有底部操作按钮时建议关闭） */
    showChevron?: boolean
    /** 点击卡片主体是否触发 select */
    tapToSelect?: boolean
  }>(),
  {
    showChevron: false,
    tapToSelect: true,
  },
)

const emit = defineEmits<{ select: [unknown, number] }>()
const slots = useSlots()
const hasActions = computed(() => Boolean(slots.actions))
const bodyTapable = computed(() => props.tapToSelect && !hasActions.value)

function listKey(item: unknown, idx: number) {
  const row = item as { id?: number | string }
  return row.id != null ? `id-${row.id}` : `idx-${idx}`
}

function onBodyTap(item: unknown, idx: number) {
  if (!bodyTapable.value) return
  emit('select', item, idx)
}
</script>

<style scoped>
.adm-list-wrap {
  width: 100%;
}
.adm-list-stack {
  display: flex;
  flex-direction: column;
  gap: 24rpx;
}
</style>
