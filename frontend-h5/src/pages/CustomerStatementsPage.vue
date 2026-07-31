<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { listMyStatements, type CustomerStatementListItem } from '@/api/customer'

const { t } = useI18n()
const router = useRouter()

const loading = ref(false)
const items = ref<CustomerStatementListItem[]>([])
const query = reactive({ status: '', offset: 0, limit: 50 })

const page = computed(() => Math.floor(query.offset / query.limit) + 1)

const statusTabs = computed(() => [
  { name: 'all', title: t('customer.statements.allStatus') },
  { name: 'draft', title: t('customer.statements.draft') },
  { name: 'confirmed', title: t('customer.statements.confirmed') },
  { name: 'paid', title: t('customer.statements.paid') },
])

const activeStatusTab = computed(() => query.status || 'all')

function statusLabel(s: string) {
  const map: Record<string, string> = {
    draft: t('customer.statements.draft'),
    confirmed: t('customer.statements.confirmed'),
    paid: t('customer.statements.paid'),
  }
  return map[s] || s || '—'
}

function periodLabel(x: CustomerStatementListItem) {
  const s = x.period_start || '—'
  const e = x.period_end || '—'
  return `${s} ~ ${e}`
}

async function load(reset = false) {
  if (loading.value) return
  if (reset) query.offset = 0
  loading.value = true
  try {
    const res = await listMyStatements({
      status: query.status || undefined,
      offset: query.offset,
      limit: query.limit,
    })
    items.value = res.items || []
  } finally {
    loading.value = false
  }
}

function openDetail(id: number) {
  router.push({ name: 'customerStatementDetail', params: { id } })
}

function onPrev() {
  if (query.offset <= 0) return
  query.offset = Math.max(0, query.offset - query.limit)
  load(false)
}

function onNext() {
  if (items.value.length < query.limit) return
  query.offset += query.limit
  load(false)
}

function onStatusTabChange(name: string | number) {
  const next = String(name) === 'all' ? '' : String(name)
  if (query.status === next) return
  query.status = next
  load(true)
}

onMounted(() => load(true))
</script>

<template>
  <div>
    <van-tabs :active="activeStatusTab" shrink @change="onStatusTabChange">
      <van-tab v-for="tab in statusTabs" :key="tab.name" :name="tab.name" :title="tab.title" />
    </van-tabs>

    <div class="mt-3">
      <van-loading v-if="loading" class="mx-auto" />
      <van-empty v-else-if="items.length === 0" :description="t('customer.statements.noData')" />
      <van-cell-group v-else inset>
        <van-cell
          v-for="x in items"
          :key="x.id"
          :title="x.code"
          :label="periodLabel(x)"
          is-link
          @click="openDetail(x.id)"
        >
          <template #value>
            <div class="flex flex-col items-end gap-1">
              <div class="text-[13px]">¥{{ x.total_amount }}</div>
              <van-tag plain type="primary">{{ statusLabel(x.status) }}</van-tag>
            </div>
          </template>
        </van-cell>
      </van-cell-group>
    </div>

    <div class="mt-4 flex items-center justify-center gap-3">
      <van-button size="small" :disabled="query.offset <= 0" @click="onPrev">{{ t('customer.statements.prevPage') }}</van-button>
      <div class="text-[13px] text-zinc-600">{{ t('customer.statements.page', { page }) }}</div>
      <van-button size="small" :disabled="items.length < query.limit" @click="onNext">{{ t('customer.statements.nextPage') }}</van-button>
    </div>

    <div class="mt-6 px-4">
      <van-button block @click="router.push({ name: 'customerOrder' })">{{ t('customer.statements.return') }}</van-button>
    </div>
  </div>
</template>
