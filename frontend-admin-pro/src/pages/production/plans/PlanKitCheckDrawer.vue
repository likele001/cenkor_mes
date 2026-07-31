<template>
  <el-drawer :model-value="open" size="980px" title="齐套检查" destroy-on-close @update:model-value="emit('update:open', $event)">
    <div v-loading="loading">
      <div v-if="kitData" class="space-y-3">
        <div class="border rounded p-3 bg-white">
          <div class="flex items-center justify-between gap-3 flex-wrap">
            <div>
              <div class="font-medium">{{ kitData.plan_code }}</div>
              <div class="text-xs text-zinc-500 mt-1">
                <span v-if="kitData.order_code">{{ kitData.order_code }}</span>
                <span v-if="kitData.customer_name"> · {{ kitData.customer_name }}</span>
              </div>
            </div>
            <div class="flex items-center gap-2 flex-wrap">
              <el-button
                v-if="kitCanRelease"
                type="success"
                :loading="releasingId === planId"
                @click="emit('releasePlan', planId!)"
              >
                确认下发（生成工单）
              </el-button>
              <el-select :model-value="supplierId" clearable filterable placeholder="选择供应商" style="width: 260px" @update:model-value="emit('update:supplierId', $event as any)">
                <el-option v-for="s in suppliers" :key="s.id" :label="partyOptionLabel(s)" :value="s.id" />
              </el-select>
              <el-button type="primary" :loading="creating" :disabled="!canCreatePurchase" @click="emit('createPurchase')">
                一键生成采购单
              </el-button>
            </div>
          </div>
        </div>

        <el-alert
          v-if="kitData.missing_boms.length"
          title="存在未配置 BOM 的产品型号，需先补齐 BOM 后再生成采购单"
          type="warning"
          show-icon
          :closable="false"
        />

        <div class="hidden lg:block space-y-3">
          <div class="border rounded bg-white">
            <div class="px-3 py-2 border-b bg-zinc-50 flex items-center justify-between">
              <div class="font-medium">已生成采购单</div>
              <div class="text-xs text-zinc-500">
                <span>数量：{{ purchaseOrders.length }}</span>
                <span class="ml-3">已入库：{{ poReceivedCount }}</span>
              </div>
            </div>
            <div v-loading="loadingPOs">
              <el-table v-if="purchaseOrders.length" class="w-full" :data="purchaseOrders" border>
                <el-table-column prop="code" label="采购单号" min-width="220" />
                <el-table-column label="供应商" min-width="220">
                  <template #default="{ row }"><span>{{ row.supplier_name || '-' }}</span></template>
                </el-table-column>
                <el-table-column label="状态" width="140">
                  <template #default="{ row }">
                    <el-tag :type="poStatusTag(row.status)">{{ poStatusLabel(row.status) }}</el-tag>
                  </template>
                </el-table-column>
                <el-table-column label="入库进度" width="180">
                  <template #default="{ row }"><span>{{ row.received_qty }} / {{ row.total_qty }}</span></template>
                </el-table-column>
                <el-table-column prop="created_at" label="创建时间" width="180" />
                <el-table-column label="操作" width="120" fixed="right">
                  <template #default="{ row }">
                    <el-button size="small" type="primary" @click="router.push(`/purchase/orders/${row.id}`)">详情</el-button>
                  </template>
                </el-table-column>
              </el-table>
              <el-empty v-if="!purchaseOrders.length" description="暂无采购单（可用上方按钮一键生成）" />
            </div>
          </div>

          <div class="border rounded bg-white">
            <div class="px-3 py-2 border-b bg-zinc-50 flex items-center justify-between">
              <div class="font-medium">缺料明细</div>
              <div class="text-xs text-zinc-500">
                <span>缺料行：{{ shortageCount }}</span>
                <span class="ml-3">过滤后：{{ kitItems.length }}</span>
              </div>
            </div>
            <el-table class="w-full" :data="kitItems" border>
              <el-table-column prop="material_code" label="物料编码" width="180" />
              <el-table-column prop="material_name" label="物料名称" min-width="220" />
              <el-table-column prop="unit" label="单位" width="100" />
              <el-table-column prop="spec" label="规格" min-width="180" />
              <el-table-column prop="demand_qty" label="需求" width="110" />
              <el-table-column prop="stock_qty" label="库存" width="110" />
              <el-table-column label="缺口" width="120">
                <template #default="{ row }">
                  <el-tag :type="row.shortage_qty > 0 ? 'danger' : 'success'">{{ row.shortage_qty }}</el-tag>
                </template>
              </el-table-column>
              <el-table-column label="供应商" width="220">
                <template #default="{ row }"><span>{{ supplierLabel(row.supplier_id) }}</span></template>
              </el-table-column>
            </el-table>
          </div>
        </div>

        <el-collapse v-model="mobileCollapse" class="lg:hidden border border-[var(--el-border-color-light)] rounded-lg overflow-hidden">
          <el-collapse-item name="po">
            <template #title>
              <span class="font-medium">已生成采购单</span>
              <span class="text-xs text-zinc-500 ml-2">({{ purchaseOrders.length }})</span>
            </template>
            <div v-loading="loadingPOs" class="space-y-2">
              <template v-if="purchaseOrders.length">
                <div v-for="row in purchaseOrders" :key="row.id" class="admin-mobile-row">
                  <div class="admin-mobile-row__head">
                    <div class="min-w-0">
                      <div class="font-medium text-sm truncate">{{ row.code }}</div>
                      <div class="text-xs text-zinc-500">{{ row.supplier_name || '—' }}</div>
                    </div>
                    <el-tag :type="poStatusTag(row.status)" size="small">{{ poStatusLabel(row.status) }}</el-tag>
                  </div>
                  <dl class="admin-mobile-kv">
                    <dt>入库</dt><dd>{{ row.received_qty }} / {{ row.total_qty }}</dd>
                    <dt>创建</dt><dd>{{ row.created_at || '—' }}</dd>
                  </dl>
                  <div class="admin-mobile-actions">
                    <el-button size="small" type="primary" @click="router.push(`/purchase/orders/${row.id}`)">详情</el-button>
                  </div>
                </div>
              </template>
              <el-empty v-else description="暂无采购单" :image-size="64" />
            </div>
          </el-collapse-item>
          <el-collapse-item name="kit">
            <template #title>
              <span class="font-medium">缺料明细</span>
              <span class="text-xs text-zinc-500 ml-2">缺料 {{ shortageCount }} · 显示 {{ kitItems.length }}</span>
            </template>
            <div class="space-y-2">
              <div v-for="(row, idx) in kitItems" :key="`${row.material_code}-${idx}`" class="admin-mobile-row">
                <div class="font-medium text-sm">{{ row.material_name || row.material_code }}</div>
                <div class="text-xs text-zinc-500">{{ row.material_code }} · {{ row.spec || '—' }}</div>
                <dl class="admin-mobile-kv mt-2">
                  <dt>需求</dt><dd>{{ row.demand_qty }} {{ row.unit || '' }}</dd>
                  <dt>库存</dt><dd>{{ row.stock_qty }}</dd>
                  <dt>缺口</dt><dd><el-tag :type="row.shortage_qty > 0 ? 'danger' : 'success'" size="small">{{ row.shortage_qty }}</el-tag></dd>
                  <dt>供应商</dt><dd class="text-left">{{ supplierLabel(row.supplier_id) }}</dd>
                </dl>
              </div>
              <el-empty v-if="!kitItems.length" description="无缺料行" :image-size="64" />
            </div>
          </el-collapse-item>
        </el-collapse>
      </div>
      <el-empty v-else description="暂无数据" />
    </div>
  </el-drawer>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { type KittingOut, type PlanKittingPurchaseOrderOut } from '@/api/purchase'
import { type SupplierOut } from '@/api/materials'
import { partyOptionLabel } from '@/utils/display'

const { t } = useI18n()
const router = useRouter()

const props = defineProps<{
  open: boolean
  loading: boolean
  creating: boolean
  loadingPOs: boolean
  planId: number
  supplierId: number | null
  kitData: KittingOut | null
  purchaseOrders: PlanKittingPurchaseOrderOut[]
  suppliers: SupplierOut[]
  releasingId: number | null
  kitCanRelease: boolean
}>()

const emit = defineEmits<{
  (e: 'update:open', val: boolean): void
  (e: 'update:supplierId', val: number | null): void
  (e: 'releasePlan', planId: number): void
  (e: 'createPurchase'): void
}>()

const mobileCollapse = ref(['po', 'kit'])

const shortageCount = computed(() => (props.kitData?.items || []).filter((x) => x.shortage_qty > 0).length)
const kitItems = computed(() => {
  const all = props.kitData?.items || []
  if (!props.supplierId) return all
  return all.filter((x) => x.supplier_id === props.supplierId)
})
const poReceivedCount = computed(() => props.purchaseOrders.filter((x) => x.status === 'received').length)

const supMap = computed(() => new Map(props.suppliers.map((s) => [s.id, s])))
function supplierLabel(id: number | null) {
  if (!id) return '-'
  const s = supMap.value.get(id)
  if (!s) return String(id)
  return partyOptionLabel(s)
}

function poStatusLabel(s: string) {
  if (s === 'draft') return t('production.plans.poStatusDraft')
  if (s === 'confirmed') return t('production.plans.poStatusConfirmed')
  if (s === 'partial_received') return t('production.plans.poStatusPartial')
  if (s === 'received') return t('production.plans.poStatusReceived')
  if (s === 'canceled') return t('production.plans.poStatusCanceled')
  return s || '-'
}

function poStatusTag(s: string) {
  if (s === 'draft') return 'info'
  if (s === 'confirmed') return 'warning'
  if (s === 'partial_received') return 'warning'
  if (s === 'received') return 'success'
  if (s === 'canceled') return 'danger'
  return 'info'
}

const canCreatePurchase = computed(() => {
  if (!props.kitData) return false
  if (props.creating) return false
  if (props.kitData.missing_boms.length) return false
  const anyShort = (props.kitData.items || []).some((x) => x.shortage_qty > 0)
  if (!anyShort) return false
  return true
})
</script>
