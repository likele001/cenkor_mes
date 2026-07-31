<script setup lang="ts">
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { ElMessage } from 'element-plus'
import type { OpportunityActivityOut, OpportunityOut } from '@/api/production'

const { t } = useI18n()

const props = defineProps<{
  modelValue: boolean
  opportunity: OpportunityOut | null
  loading: boolean
  items: OpportunityActivityOut[]
}>()

const emit = defineEmits<{
  (e: 'update:modelValue', v: boolean): void
  (e: 'add', payload: { action_type: string; content: string; next_follow_up_at: string | null }): void
}>()

const saving = ref(false)
const form = ref({
  action_type: 'note',
  content: '',
  next_follow_up_at: null as string | null,
})

function handleAdd() {
  const content = String(form.value.content || '').trim()
  if (!content) {
    ElMessage.error(t('production.customers.pleaseInputFollowContent'))
    return
  }
  saving.value = true
  emit('add', {
    action_type: form.value.action_type,
    content,
    next_follow_up_at: form.value.next_follow_up_at || null,
  })
  form.value.content = ''
}
</script>

<template>
  <el-drawer
    :model-value="modelValue"
    @update:model-value="emit('update:modelValue', $event)"
    title="跟进记录"
    size="560px"
  >
    <div v-if="props.opportunity" class="text-sm text-zinc-500 mb-2">
      {{ props.opportunity.code }} · {{ props.opportunity.title }}
    </div>
    <el-form :model="form" label-width="70px">
      <el-form-item label="类型">
        <el-select v-model="form.action_type" style="width: 140px">
          <el-option label="备注" value="note" />
          <el-option label="电话" value="call" />
          <el-option label="拜访" value="visit" />
        </el-select>
      </el-form-item>
      <el-form-item label="内容">
        <el-input v-model="form.content" type="textarea" :rows="3" />
      </el-form-item>
      <el-form-item label="下次跟进">
        <el-date-picker v-model="form.next_follow_up_at" type="datetime" value-format="YYYY-MM-DDTHH:mm:ss" style="width: 100%" />
      </el-form-item>
      <el-form-item>
        <el-button type="primary" :loading="saving" @click="handleAdd">{{ t('production.common.create') }}</el-button>
      </el-form-item>
    </el-form>

    <el-divider />

    <div v-loading="props.loading">
      <el-table class="hidden lg:block w-full" :data="props.items" border>
        <el-table-column prop="created_at" label="时间" width="170" />
        <el-table-column prop="action_type" label="类型" width="80" />
        <el-table-column prop="created_by_name" label="记录人" width="100" />
        <el-table-column prop="content" label="内容" min-width="220" />
      </el-table>
      <div class="lg:hidden space-y-3">
        <div v-for="(row, idx) in props.items" :key="idx" class="admin-mobile-row">
          <div class="admin-mobile-row__head">
            <span class="text-xs text-el-placeholder">{{ row.created_at }}</span>
            <el-tag size="small">{{ row.action_type }}</el-tag>
          </div>
          <div class="text-xs text-el-placeholder">记录人：{{ row.created_by_name || '—' }}</div>
          <p class="text-sm text-el-regular m-0 mt-1">{{ row.content }}</p>
        </div>
        <el-empty v-if="!props.loading && !props.items.length" :description="t('production.customers.noActivities')" />
      </div>
    </div>
  </el-drawer>
</template>
