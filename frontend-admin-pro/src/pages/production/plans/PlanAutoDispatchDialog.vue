<template>
  <el-dialog :model-value="open" width="860px" title="自动派工结果" destroy-on-close @update:model-value="emit('update:open', $event)">
    <div v-loading="loading">
      <el-alert
        v-if="result"
        class="mb-3"
        :title="`本次派工：${result.assigned_count} 条（参与任务：${result.task_count}，工期工作日：${result.span_workdays}）`"
        type="success"
        show-icon
        :closable="false"
      />
      <el-alert v-if="result && result.overloads.length" class="mb-3" title="存在超负荷项，请优先处理" type="warning" show-icon :closable="false" />

      <div class="hidden lg:block space-y-3">
        <el-table v-if="result && result.overloads.length" :data="result.overloads" border>
          <el-table-column prop="type" label="类型" width="120" />
          <el-table-column prop="name" label="对象" min-width="220" />
          <el-table-column prop="daily_minutes" label="日负荷(分)" width="140" />
          <el-table-column prop="capacity" label="日产能(分)" width="140" />
        </el-table>
        <el-table v-if="result" :data="result.workshops" border>
          <el-table-column prop="workshop" label="车间" min-width="160" />
          <el-table-column prop="daily_minutes" label="日负荷(分)" width="140" />
          <el-table-column prop="capacity" label="日产能(分)" width="140" />
          <el-table-column label="状态" width="120">
            <template #default="{ row }">
              <el-tag :type="row.overload ? 'danger' : 'success'">{{ row.overload ? '超负荷' : '正常' }}</el-tag>
            </template>
          </el-table-column>
        </el-table>
        <el-table v-if="result" :data="result.users" border>
          <el-table-column prop="name" label="人员" min-width="160" />
          <el-table-column prop="daily_minutes" label="日负荷(分)" width="140" />
          <el-table-column prop="capacity" label="日产能(分)" width="140" />
          <el-table-column label="状态" width="120">
            <template #default="{ row }">
              <el-tag :type="row.overload ? 'danger' : 'success'">{{ row.overload ? '超负荷' : '正常' }}</el-tag>
            </template>
          </el-table-column>
        </el-table>
      </div>

      <el-collapse
        v-if="result"
        v-model="mobileCollapse"
        class="lg:hidden border border-[var(--el-border-color-light)] rounded-lg overflow-hidden"
      >
        <el-collapse-item v-if="result.overloads.length" name="overload">
          <template #title>
            <span class="font-medium">超负荷项</span>
            <span class="text-xs text-zinc-500 ml-2">({{ result.overloads.length }})</span>
          </template>
          <div class="space-y-2">
            <div v-for="(row, i) in result.overloads" :key="`ol-${i}-${row.name}`" class="admin-mobile-row">
              <div class="font-medium text-sm">{{ row.type }} · {{ row.name }}</div>
              <dl class="admin-mobile-kv mt-2">
                <dt>日负荷</dt><dd>{{ row.daily_minutes }} 分</dd>
                <dt>日产能</dt><dd>{{ row.capacity }} 分</dd>
              </dl>
            </div>
          </div>
        </el-collapse-item>
        <el-collapse-item name="ws">
          <template #title>
            <span class="font-medium">车间负荷</span>
            <span class="text-xs text-zinc-500 ml-2">({{ result.workshops.length }})</span>
          </template>
          <div class="space-y-2">
            <div v-for="(row, i) in result.workshops" :key="`adw-${i}-${row.workshop}`" class="admin-mobile-row">
              <div class="admin-mobile-row__head">
                <div class="font-medium text-sm">{{ row.workshop }}</div>
                <el-tag :type="row.overload ? 'danger' : 'success'" size="small">{{ row.overload ? '超负荷' : '正常' }}</el-tag>
              </div>
              <dl class="admin-mobile-kv mt-2">
                <dt>日负荷</dt><dd>{{ row.daily_minutes }} 分</dd>
                <dt>日产能</dt><dd>{{ row.capacity }} 分</dd>
              </dl>
            </div>
          </div>
        </el-collapse-item>
        <el-collapse-item name="users">
          <template #title>
            <span class="font-medium">人员负荷</span>
            <span class="text-xs text-zinc-500 ml-2">({{ result.users.length }})</span>
          </template>
          <div class="space-y-2">
            <div v-for="(row, i) in result.users" :key="`adu-${i}-${row.name}`" class="admin-mobile-row">
              <div class="admin-mobile-row__head">
                <div class="font-medium text-sm">{{ row.name }}</div>
                <el-tag :type="row.overload ? 'danger' : 'success'" size="small">{{ row.overload ? '超负荷' : '正常' }}</el-tag>
              </div>
              <dl class="admin-mobile-kv mt-2">
                <dt>日负荷</dt><dd>{{ row.daily_minutes }} 分</dd>
                <dt>日产能</dt><dd>{{ row.capacity }} 分</dd>
              </dl>
            </div>
          </div>
        </el-collapse-item>
      </el-collapse>
    </div>
  </el-dialog>
</template>

<script setup lang="ts">
import { ref } from 'vue'

defineProps<{
  open: boolean
  loading: boolean
  result: null | {
    assigned_count: number
    task_count: number
    span_workdays: number
    users: any[]
    workshops: any[]
    overloads: any[]
  }
}>()

const emit = defineEmits<{
  (e: 'update:open', val: boolean): void
}>()

const mobileCollapse = ref(['ws', 'users'])
</script>
