<template>
  <div class="flex items-center gap-1">
    <!-- 主要操作（1-2 个，直接显示按钮） -->
    <template v-for="(action, idx) in visiblePrimaryActions" :key="'primary-' + idx">
      <el-button
        v-bind="action.props || {}"
        :size="action.size || 'small'"
        :type="action.type || 'default'"
        :disabled="action.disabled"
        :loading="action.loading"
        @click="action.handler"
      >
        {{ action.label }}
      </el-button>
    </template>

    <!-- 更多操作下拉 -->
    <el-dropdown v-if="moreActions.length" trigger="click" @command="handleMore">
      <el-button size="small">
        <el-icon><MoreFilled /></el-icon>
      </el-button>
      <template #dropdown>
        <el-dropdown-menu>
          <el-dropdown-item
            v-for="(action, idx) in moreActions"
            :key="'more-' + idx"
            :command="idx"
            :disabled="action.disabled"
            :divided="action.divided"
          >
            {{ action.label }}
          </el-dropdown-item>
        </el-dropdown-menu>
      </template>
    </el-dropdown>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { MoreFilled } from '@element-plus/icons-vue'
import type { ButtonProps } from 'element-plus'

export interface ActionItem {
  label: string
  handler: () => void
  type?: ButtonProps['type']
  size?: 'small' | 'default' | 'large'
  disabled?: boolean
  loading?: boolean
  props?: Record<string, unknown>
  divided?: boolean
}

const props = withDefaults(
  defineProps<{
    primaryActions?: ActionItem[]
    moreActions?: ActionItem[]
  }>(),
  {
    primaryActions: () => [],
    moreActions: () => [],
  }
)

const visiblePrimaryActions = computed(() => props.primaryActions.slice(0, 2))

function handleMore(idx: number) {
  const action = props.moreActions[idx]
  if (action && !action.disabled) {
    action.handler()
  }
}
</script>
