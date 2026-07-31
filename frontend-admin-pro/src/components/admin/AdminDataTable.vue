<template>
  <div class="admin-data-table">
    <div v-loading="loading" class="admin-data-table__body">
      <slot name="table" />
      <slot name="mobile" />
      <AdminEmpty v-if="!loading && empty" :description="resolvedEmptyText">
        <template v-if="$slots.emptyAction" #action>
          <slot name="emptyAction" />
        </template>
      </AdminEmpty>
    </div>
    <div v-if="showPagination" class="mt-4 flex justify-end">
      <el-pagination
        background
        :layout="paginationLayout"
        :page-size="pageSize"
        :total="total"
        :current-page="currentPage"
        @current-change="(p: number) => $emit('page-change', p)"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import AdminEmpty from '@/components/admin/AdminEmpty.vue'

const { t } = useI18n()

const props = withDefaults(
  defineProps<{
    loading?: boolean
    empty?: boolean
    emptyText?: string
    showPagination?: boolean
    pageSize?: number
    total?: number
    currentPage?: number
    paginationLayout?: string
  }>(),
  {
    loading: false,
    empty: false,
    emptyText: '',
    showPagination: true,
    pageSize: 50,
    total: 0,
    currentPage: 1,
    paginationLayout: 'prev, pager, next',
  }
)

const resolvedEmptyText = computed(() => props.emptyText || t('common.noDataText'))

defineEmits<{
  'page-change': [page: number]
}>()
</script>
