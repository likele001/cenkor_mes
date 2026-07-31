<template>
  <el-drawer v-model="visible" size="980px" :title="resolvedTitle" destroy-on-close @closed="emit('closed')">
    <div v-loading="loading">
      <div v-if="data" class="space-y-4">
        <div class="border rounded p-3 bg-white">
          <div class="flex items-start justify-between gap-3 flex-wrap">
            <div>
              <div class="font-medium text-base">
                {{ data.plan_code || t('planReadiness.readyPreview') }}
                <el-tag v-if="data.ready" type="success" class="ml-2">{{ t('planReadiness.readyToRelease') }}</el-tag>
                <el-tag v-else type="warning" class="ml-2">{{ t('planReadiness.pendingProcess') }}</el-tag>
              </div>
              <div class="text-xs text-zinc-500 mt-1">
                <span v-if="data.order_code">{{ t('planReadiness.order') }} {{ data.order_code }}</span>
                <span v-if="data.customer_name"> · {{ data.customer_name }}</span>
              </div>
              <div v-if="data.blockers?.length" class="text-sm text-amber-700 mt-2">
                {{ data.blockers.join('；') }}
              </div>
            </div>
            <div v-if="showRelease && planId && canRelease" class="flex gap-2">
              <el-button type="success" :loading="releasing" @click="onReleaseClick">{{ t('planReadiness.confirmRelease') }}</el-button>
            </div>
          </div>
        </div>

        <el-tabs v-model="activeTab">
          <el-tab-pane name="kitting">
            <template #label>
              {{ t('planReadiness.kitting') }}
              <el-badge
                v-if="kittingIssueCount"
                :value="kittingIssueCount"
                class="ml-1"
                type="danger"
              />
            </template>
            <div class="space-y-3">
              <div v-if="planId" class="space-y-3">
                <div class="flex items-center gap-2 flex-wrap">
                  <el-select
                    v-model="supplierId"
                    clearable
                    filterable
                    :placeholder="t('planReadiness.selectSupplier')"
                    style="width: 260px"
                  >
                    <el-option
                      v-for="s in suppliers"
                      :key="s.id"
                      :label="partyOptionLabel(s)"
                      :value="s.id"
                    />
                  </el-select>
                  <el-button type="primary" :loading="creatingPurchase" :disabled="!canCreatePurchase" @click="createPurchase">
                    {{ t('planReadiness.generatePurchaseOrder') }}
                  </el-button>
                </div>
                <div v-if="purchaseOrders.length" class="border rounded bg-white">
                  <div class="px-3 py-2 border-b bg-zinc-50 text-sm font-medium">{{ t('planReadiness.thisPlanPurchaseOrders') }}</div>
                  <el-table :data="purchaseOrders" border size="small">
                    <el-table-column prop="code" :label="t('planReadiness.purchaseOrderCode')" min-width="180" />
                    <el-table-column prop="supplier_name" :label="t('planReadiness.supplier')" min-width="140" />
                    <el-table-column :label="t('common.edit')" width="100">
                      <template #default="{ row }">
                        <el-button link type="primary" @click="router.push(`/purchase/orders/${row.id}`)">{{ t('planReadiness.detail') }}</el-button>
                      </template>
                    </el-table-column>
                  </el-table>
                </div>
              </div>

              <el-alert
                v-if="data.kitting.missing_boms.length"
                :title="t('planReadiness.missingBomAlert')"
                type="warning"
                show-icon
                :closable="false"
              />
              <el-table
                v-if="data.kitting.missing_boms.length"
                :data="data.kitting.missing_boms"
                border
                size="small"
              >
                <el-table-column :label="t('planReadiness.productOrSku')" min-width="280">
                  <template #default="{ row }">
                    <div class="font-medium">{{ row.display_label || row.product_name || row.sku_name }}</div>
                    <div v-if="row.sku_code" class="text-xs text-zinc-400">{{ t('planReadiness.code') }} {{ row.sku_code }}</div>
                  </template>
                </el-table-column>
                <el-table-column :label="t('common.edit')" width="120">
                  <template #default="{ row }">
                    <el-button link type="primary" @click="router.push('/master/boms')">{{ t('planReadiness.goToMaintainBom') }}</el-button>
                  </template>
                </el-table-column>
              </el-table>

              <div class="border rounded bg-white">
                <div class="px-3 py-2 border-b bg-zinc-50 font-medium">{{ t('planReadiness.materialDemandAndStock') }}</div>
                <el-table :data="shortageItems" border size="small" max-height="360">
                  <el-table-column prop="material_code" :label="t('planReadiness.materialCode')" width="150" />
                  <el-table-column prop="material_name" :label="t('planReadiness.materialName')" min-width="180" />
                  <el-table-column prop="demand_qty" :label="t('planReadiness.demand')" width="90" />
                  <el-table-column prop="stock_qty" :label="t('planReadiness.stock')" width="90" />
                  <el-table-column :label="t('planReadiness.shortage')" width="90">
                    <template #default="{ row }">
                      <el-tag :type="row.shortage_qty > 0 ? 'danger' : 'success'" size="small">
                        {{ row.shortage_qty }}
                      </el-tag>
                    </template>
                  </el-table-column>
                </el-table>
                <div v-if="!shortageItems.length" class="p-4 text-sm text-zinc-500">{{ t('planReadiness.noMaterialDemand') }}</div>
              </div>
            </div>
          </el-tab-pane>

          <el-tab-pane name="process">
            <template #label>
              {{ t('planReadiness.processAndPrice') }}
              <el-badge
                v-if="processIssueCount"
                :value="processIssueCount"
                class="ml-1"
                type="danger"
              />
            </template>
            <div class="space-y-3">
              <el-alert
                v-if="data.process.missing_routes.length"
                :title="t('planReadiness.missingRouteAlert')"
                type="warning"
                show-icon
                :closable="false"
              />
              <el-table
                v-if="data.process.missing_routes.length"
                :data="data.process.missing_routes"
                border
                size="small"
              >
                <el-table-column prop="product_code" :label="t('planReadiness.productCode')" width="140" />
                <el-table-column prop="product_name" :label="t('planReadiness.productName')" min-width="220" />
                <el-table-column :label="t('common.edit')" width="120">
                  <template #default>
                    <el-button link type="primary" @click="router.push('/master/process-routes')">{{ t('planReadiness.goToConfigureRoute') }}</el-button>
                  </template>
                </el-table-column>
              </el-table>

              <el-alert
                v-if="data.process.missing_prices.length"
                :title="t('planReadiness.missingPriceAlert')"
                type="warning"
                show-icon
                :closable="false"
              />
              <el-table
                v-if="data.process.missing_prices.length"
                :data="data.process.missing_prices"
                border
                size="small"
              >
                <el-table-column :label="t('planReadiness.productOrSku')" min-width="200">
                  <template #default="{ row }">
                    <div>{{ row.display_label || row.sku_name }}</div>
                    <div v-if="row.sku_code" class="text-xs text-zinc-400">{{ t('planReadiness.code') }} {{ row.sku_code }}</div>
                  </template>
                </el-table-column>
                <el-table-column :label="t('planReadiness.process')" min-width="120">
                  <template #default="{ row }">{{ row.process_name }}</template>
                </el-table-column>
                <el-table-column :label="t('common.edit')" width="120">
                  <template #default="{ row }">
                    <el-button
                      link
                      type="primary"
                      @click="router.push({ path: '/production/process-prices', query: { sku_id: row.sku_id } })"
                    >
                      {{ t('planReadiness.goToSetPrice') }}
                    </el-button>
                  </template>
                </el-table-column>
              </el-table>

              <el-empty
                v-if="!data.process.missing_routes.length && !data.process.missing_prices.length"
                :description="t('planReadiness.routeAndPriceReady')"
              />
            </div>
          </el-tab-pane>
        </el-tabs>
      </div>
    </div>
  </el-drawer>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { plansApi, type PlanReadinessOut } from '@/api/plans'
import { purchaseApi } from '@/api/purchase'
import { materialsApi } from '@/api/materials'
import { partyOptionLabel } from '@/utils/display'

const { t } = useI18n()

const props = withDefaults(
  defineProps<{
    modelValue: boolean
    planId?: number | null
    orderId?: number | null
    title?: string
    showRelease?: boolean
    canRelease?: boolean
    releasing?: boolean
  }>(),
  {
    planId: null,
    orderId: null,
    title: '投产就绪检查',
    showRelease: false,
    canRelease: false,
    releasing: false,
  },
)
const resolvedTitle = computed(() => props.title === '投产就绪检查' ? t('planReadiness.planReadiness') : props.title)

const emit = defineEmits<{
  'update:modelValue': [boolean]
  closed: []
  release: [number, { allow_shortage: boolean }]
}>()

const router = useRouter()
const loading = ref(false)
const data = ref<PlanReadinessOut | null>(null)
const activeTab = ref('kitting')
const supplierId = ref<number | null>(null)
const creatingPurchase = ref(false)
const suppliers = ref<{ id: number; code: string; name: string }[]>([])
const purchaseOrders = ref<{ id: number; code: string; supplier_name?: string | null }[]>([])

const visible = computed({
  get: () => props.modelValue,
  set: (v) => emit('update:modelValue', v),
})

const kittingIssueCount = computed(
  () => (data.value?.kitting.shortage_count || 0) + (data.value?.kitting.missing_bom_count || 0),
)
const processIssueCount = computed(
  () => (data.value?.process.missing_route_count || 0) + (data.value?.process.missing_price_count || 0),
)

const shortageItems = computed(() => {
  const items = data.value?.kitting.items || []
  return items.filter((x) => x.shortage_qty > 0)
})

const canCreatePurchase = computed(() => {
  if (!props.planId || !data.value) return false
  if (data.value.kitting.missing_boms.length) return false
  return (data.value.kitting.shortage_count || 0) > 0
})

async function loadSuppliers() {
  const res = await materialsApi.listSuppliers({ keyword: '', offset: 0, limit: 200, include_inactive: true })
  suppliers.value = res.items
}

async function loadPurchaseOrders() {
  if (!props.planId) {
    purchaseOrders.value = []
    return
  }
  try {
    const res = await purchaseApi.listKittingPurchaseOrders(props.planId)
    purchaseOrders.value = res.items || []
  } catch {
    purchaseOrders.value = []
  }
}

async function load() {
  loading.value = true
  data.value = null
  purchaseOrders.value = []
  try {
    if (props.planId) {
      data.value = await plansApi.getPlanReadiness(props.planId)
      await loadPurchaseOrders()
    } else if (props.orderId) {
      data.value = await plansApi.previewPlanReadiness(props.orderId)
    }
    if (data.value && !data.value.kitting.ok) activeTab.value = 'kitting'
    else if (data.value && !data.value.process.ok) activeTab.value = 'process'
  } catch (e: any) {
    ElMessage.error(e?.message || t('planReadiness.loadFailed'))
    visible.value = false
  } finally {
    loading.value = false
  }
}

async function onReleaseClick() {
  if (!props.planId) return
  const shortage = data.value?.kitting.shortage_count || 0
  if (shortage > 0) {
    const ok = await ElMessageBox.confirm(
      `${t('planReadiness.shortageReleaseConfirm')} ${shortage} ${t('planReadiness.shortageItems')}`,
      t('planReadiness.shortageConfirmTitle'),
      { type: 'warning', confirmButtonText: t('planReadiness.stillRelease'), cancelButtonText: t('common.cancel') },
    )
      .then(() => true)
      .catch(() => false)
    if (!ok) return
  } else {
    const ok = await ElMessageBox.confirm(
      `${t('planReadiness.confirmReleasePlan')}「${data.value?.plan_code || props.planId}」${t('planReadiness.willGenerateWorkOrders')}`,
      t('planReadiness.confirmReleaseTitle'),
      { type: 'warning' },
    )
      .then(() => true)
      .catch(() => false)
    if (!ok) return
  }
  emit('release', props.planId, { allow_shortage: shortage > 0 })
}

async function createPurchase() {
  if (!props.planId) return
  creatingPurchase.value = true
  try {
    const res = await purchaseApi.createPurchaseFromKitting(props.planId, supplierId.value)
    if (!res.items.length) {
      ElMessage.success(t('planReadiness.noShortageNoPurchase'))
      return
    }
    ElMessage.success(`${t('planReadiness.generatedPurchaseOrders')} ${res.items.length} ${t('planReadiness.purchaseOrdersCount')}`)
    await loadPurchaseOrders()
    if (res.items.length === 1) router.push(`/purchase/orders/${res.items[0].id}`)
  } finally {
    creatingPurchase.value = false
  }
}

watch(
  () => [props.modelValue, props.planId, props.orderId] as const,
  ([open]) => {
    if (open) {
      loadSuppliers()
      load()
    }
  },
)
</script>
