<template>
  <div class="admin-empty flex flex-col items-center justify-center py-10 px-4 text-center">
    <el-icon :size="48" class="admin-empty__icon mb-3 opacity-60">
      <Box />
    </el-icon>
    <p class="text-[14px] text-[var(--admin-brand-subtitle)]">{{ resolvedDescription }}</p>
    <div v-if="$slots.action || hasBuiltinActions" class="mt-4 flex flex-wrap items-center justify-center gap-3">
      <slot name="action">
        <el-button v-if="createText" type="primary" @click="createAction?.()">
          {{ createText }}
        </el-button>
        <el-button v-if="importText" @click="importAction?.()">
          {{ importText }}
        </el-button>
        <el-button v-if="guideText" link @click="guideAction?.()">
          {{ guideText }}
        </el-button>
      </slot>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { Box } from '@element-plus/icons-vue'

const { t } = useI18n()

const props = withDefaults(
  defineProps<{
    description?: string
    createText?: string
    createAction?: () => void
    importText?: string
    importAction?: () => void
    guideText?: string
    guideAction?: () => void
  }>(),
  {
    description: '',
    createText: '',
    createAction: undefined,
    importText: '',
    importAction: undefined,
    guideText: '',
    guideAction: undefined,
  }
)

const resolvedDescription = computed(() => props.description || t('common.noDataText'))
const hasBuiltinActions = computed(() => !!props.createText || !!props.importText || !!props.guideText)
</script>

<style scoped>
.admin-empty__icon {
  color: var(--el-color-primary);
}
</style>
