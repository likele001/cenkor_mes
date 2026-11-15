<!--
  Copyright (C) 2026 CenkorMES Project
  SPDX-License-Identifier: AGPL-3.0
  库位管理：库区 + 库位两个页签。

  为什么合成一个页面：库区只是库位的分类标签，实际配置时几乎总是「先建库区再建库位」，
  拆成两个菜单来回跳反而碍事。库区下还有库位时不允许删库区、库位下还有批次时
  不允许删库位 —— 这两条保护在后端做，前端只负责把错误提示原样弹出来。
-->
<script setup lang="ts">
import AdminPage from '@/components/admin/AdminPage.vue'
import { computed, onMounted, reactive, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { ElMessage, ElMessageBox } from 'element-plus'
import { http } from '@/utils/http'

const { t } = useI18n()

interface WarehouseOpt {
  id: number
  code: string
  name: string
}

interface Zone {
  id: number
  warehouse_id: number
  code: string
  name: string
  zone_type: string
  zone_type_label: string
  capacity: number | null
  sort_order: number
  enabled: boolean
  location_count: number
}

interface Location {
  id: number
  warehouse_id: number
  code: string
  name: string
  zone_id: number | null
  zone_code: string | null
  location_type: string
  location_type_label: string
  capacity: number | null
  is_active: boolean
  qty_on_hand: number
  sku_count: number
  usage_pct: number | null
  remark: string | null
}

interface StockRow {
  batch_id: number
  batch_no: string
  sku_code: string
  sku_name: string
  qty_on_hand: number
  qty_reserved: number
  available: number
  status: string
  expiry_date: string | null
}

const ZONE_TYPES = [
  { value: 'storage', labelKey: 'zoneTypeStorage' },
  { value: 'receiving', labelKey: 'zoneTypeReceiving' },
  { value: 'picking', labelKey: 'zoneTypePicking' },
  { value: 'inspection', labelKey: 'zoneTypeInspection' },
  { value: 'defect', labelKey: 'zoneTypeDefect' },
  { value: 'shipping', labelKey: 'zoneTypeShipping' },
] as const

const LOCATION_TYPES = [
  { value: 'zone', labelKey: 'typeZone' },
  { value: 'rack', labelKey: 'typeRack' },
  { value: 'bin', labelKey: 'typeBin' },
] as const

const activeTab = ref('locations')
const loading = ref(false)
const warehouses = ref<WarehouseOpt[]>([])
const selectedWh = ref<number | null>(null)
const zones = ref<Zone[]>([])
const locations = ref<Location[]>([])

const whName = computed(() => {
  const w = warehouses.value.find((x) => x.id === selectedWh.value)
  return w ? `${w.code} ${w.name}` : ''
})

// ── 库区弹窗 ──
const zoneDlg = reactive({
  open: false,
  saving: false,
  id: 0,
  form: { code: '', name: '', zone_type: 'storage', capacity: null as number | null, sort_order: 0, enabled: true },
})

// ── 库位弹窗 ──
const locDlg = reactive({
  open: false,
  saving: false,
  id: 0,
  form: {
    code: '',
    name: '',
    zone_id: null as number | null,
    location_type: 'bin',
    capacity: null as number | null,
    is_active: true,
    remark: '',
  },
})

// ── 库位库存抽屉 ──
const stockDrawer = reactive({
  open: false,
  loading: false,
  location: null as Location | null,
  items: [] as StockRow[],
})

async function loadWarehouses() {
  const res = await http.request<{ items: WarehouseOpt[] }>({
    url: '/admin/warehouse/warehouses',
    method: 'GET',
  })
  warehouses.value = res.items ?? []
  if (!selectedWh.value && warehouses.value.length) selectedWh.value = warehouses.value[0].id
}

async function loadZones() {
  const res = await http.request<{ items: Zone[] }>({
    url: '/admin/warehouse/zones',
    method: 'GET',
    params: selectedWh.value ? { warehouse_id: selectedWh.value } : {},
  })
  zones.value = res.items ?? []
}

async function loadLocations() {
  const res = await http.request<{ items: Location[] }>({
    url: '/admin/warehouse/locations',
    method: 'GET',
    params: selectedWh.value ? { warehouse_id: selectedWh.value } : {},
  })
  locations.value = res.items ?? []
}

async function loadAll() {
  loading.value = true
  try {
    await Promise.all([loadZones(), loadLocations()])
  } finally {
    loading.value = false
  }
}

function openZoneCreate() {
  zoneDlg.id = 0
  zoneDlg.form = { code: '', name: '', zone_type: 'storage', capacity: null, sort_order: 0, enabled: true }
  zoneDlg.open = true
}

function openZoneEdit(row: Zone) {
  zoneDlg.id = row.id
  zoneDlg.form = {
    code: row.code,
    name: row.name,
    zone_type: row.zone_type,
    capacity: row.capacity,
    sort_order: row.sort_order,
    enabled: row.enabled,
  }
  zoneDlg.open = true
}

async function saveZone() {
  if (!selectedWh.value) return
  if (!zoneDlg.form.name.trim()) {
    ElMessage.warning(t('warehouse.locations.nameRequired'))
    return
  }
  zoneDlg.saving = true
  try {
    if (zoneDlg.id) {
      await http.request({
        url: `/admin/warehouse/zones/${zoneDlg.id}`,
        method: 'PUT',
        data: {
          name: zoneDlg.form.name,
          zone_type: zoneDlg.form.zone_type,
          capacity: zoneDlg.form.capacity,
          sort_order: zoneDlg.form.sort_order,
          enabled: zoneDlg.form.enabled,
        },
      })
      ElMessage.success(t('warehouse.locations.editSuccess'))
    } else {
      await http.request({
        url: '/admin/warehouse/zones',
        method: 'POST',
        data: { ...zoneDlg.form, warehouse_id: selectedWh.value },
      })
      ElMessage.success(t('warehouse.locations.createSuccess'))
    }
    zoneDlg.open = false
    await loadAll()
  } finally {
    zoneDlg.saving = false
  }
}

async function removeZone(row: Zone) {
  try {
    await ElMessageBox.confirm(t('warehouse.locations.deleteConfirm'), t('warehouse.locations.title'), { type: 'warning' })
  } catch {
    return
  }
  await http.request({ url: `/admin/warehouse/zones/${row.id}`, method: 'DELETE' })
  ElMessage.success(t('warehouse.locations.deleteSuccess'))
  await loadAll()
}

function openLocCreate() {
  locDlg.id = 0
  locDlg.form = { code: '', name: '', zone_id: null, location_type: 'bin', capacity: null, is_active: true, remark: '' }
  locDlg.open = true
}

function openLocEdit(row: Location) {
  locDlg.id = row.id
  locDlg.form = {
    code: row.code,
    name: row.name,
    zone_id: row.zone_id,
    location_type: row.location_type,
    capacity: row.capacity,
    is_active: row.is_active,
    remark: row.remark ?? '',
  }
  locDlg.open = true
}

async function saveLocation() {
  if (!selectedWh.value) return
  if (!locDlg.form.name.trim()) {
    ElMessage.warning(t('warehouse.locations.nameRequired'))
    return
  }
  locDlg.saving = true
  try {
    if (locDlg.id) {
      await http.request({
        url: `/admin/warehouse/locations/${locDlg.id}`,
        method: 'PUT',
        data: {
          name: locDlg.form.name,
          zone_id: locDlg.form.zone_id,
          location_type: locDlg.form.location_type,
          capacity: locDlg.form.capacity,
          is_active: locDlg.form.is_active,
          remark: locDlg.form.remark || null,
        },
      })
      ElMessage.success(t('warehouse.locations.editSuccess'))
    } else {
      await http.request({
        url: '/admin/warehouse/locations',
        method: 'POST',
        data: { ...locDlg.form, warehouse_id: selectedWh.value, remark: locDlg.form.remark || null },
      })
      ElMessage.success(t('warehouse.locations.createSuccess'))
    }
    locDlg.open = false
    await loadAll()
  } finally {
    locDlg.saving = false
  }
}

async function removeLocation(row: Location) {
  try {
    await ElMessageBox.confirm(t('warehouse.locations.deleteConfirm'), t('warehouse.locations.title'), { type: 'warning' })
  } catch {
    return
  }
  await http.request({ url: `/admin/warehouse/locations/${row.id}`, method: 'DELETE' })
  ElMessage.success(t('warehouse.locations.deleteSuccess'))
  await loadAll()
}

async function openStock(row: Location) {
  stockDrawer.open = true
  stockDrawer.loading = true
  stockDrawer.location = row
  try {
    const res = await http.request<{ items: StockRow[] }>({
      url: `/admin/warehouse/locations/${row.id}/stock`,
      method: 'GET',
    })
    stockDrawer.items = res.items ?? []
  } finally {
    stockDrawer.loading = false
  }
}

onMounted(async () => {
  await loadWarehouses()
  await loadAll()
})
</script>

<template>
  <AdminPage :title="t('warehouse.locations.title')">
    <el-card shadow="never">
      <template #header>
        <div class="flex items-center gap-3 flex-wrap">
          <span class="font-medium">{{ t('warehouse.locations.title') }}</span>
          <el-select
            v-model="selectedWh"
            :placeholder="t('warehouse.locations.warehouse')"
            clearable
            style="width: 220px"
            @change="loadAll"
          >
            <el-option v-for="w in warehouses" :key="w.id" :label="`${w.code} ${w.name}`" :value="w.id" />
          </el-select>
          <span v-if="whName" class="text-xs text-el-placeholder">{{ whName }}</span>
        </div>
      </template>

      <el-tabs v-model="activeTab">
        <el-tab-pane :label="t('warehouse.locations.tabLocations')" name="locations">
          <div class="flex items-center gap-2 flex-wrap mb-3">
            <el-button type="primary" :disabled="!selectedWh" @click="openLocCreate">
              {{ t('warehouse.locations.createLocation') }}
            </el-button>
            <el-button @click="loadAll">{{ t('common.refresh') }}</el-button>
          </div>
          <el-table v-loading="loading" :data="locations" stripe style="width: 100%">
            <el-table-column prop="code" :label="t('warehouse.warehouses.code')" width="150" />
            <el-table-column prop="name" :label="t('warehouse.warehouses.name')" min-width="150" />
            <el-table-column :label="t('warehouse.locations.zone')" width="130">
              <template #default="{ row }">{{ row.zone_code || t('warehouse.locations.noZone') }}</template>
            </el-table-column>
            <el-table-column :label="t('warehouse.locations.locationType')" width="110">
              <template #default="{ row }">{{ row.location_type_label }}</template>
            </el-table-column>
            <el-table-column :label="t('warehouse.locations.capacity')" width="100">
              <template #default="{ row }">{{ row.capacity ?? '—' }}</template>
            </el-table-column>
            <el-table-column :label="t('warehouse.locations.qtyOnHand')" width="110" align="right">
              <template #default="{ row }">{{ row.qty_on_hand }}</template>
            </el-table-column>
            <el-table-column :label="t('warehouse.locations.skuCount')" width="100" align="right">
              <template #default="{ row }">{{ row.sku_count }}</template>
            </el-table-column>
            <el-table-column :label="t('warehouse.locations.usage')" width="100" align="right">
              <template #default="{ row }">
                <span v-if="row.usage_pct !== null">{{ row.usage_pct }}%</span>
                <span v-else class="text-el-placeholder">—</span>
              </template>
            </el-table-column>
            <el-table-column :label="t('warehouse.locations.isActive')" width="90" align="center">
              <template #default="{ row }">
                <el-tag :type="row.is_active ? 'success' : 'info'" size="small">
                  {{ row.is_active ? '✓' : '—' }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column :label="t('warehouse.warehouses.actions')" width="220" fixed="right">
              <template #default="{ row }">
                <el-button size="small" @click="openStock(row)">{{ t('warehouse.locations.qtyOnHand') }}</el-button>
                <el-button size="small" @click="openLocEdit(row)">{{ t('warehouse.warehouses.edit') }}</el-button>
                <el-button size="small" type="danger" @click="removeLocation(row)">
                  {{ t('warehouse.locations.delete') }}
                </el-button>
              </template>
            </el-table-column>
            <template #empty><el-empty :description="t('warehouse.locations.empty')" /></template>
          </el-table>
        </el-tab-pane>

        <el-tab-pane :label="t('warehouse.locations.tabZones')" name="zones">
          <div class="flex items-center gap-2 flex-wrap mb-3">
            <el-button type="primary" :disabled="!selectedWh" @click="openZoneCreate">
              {{ t('warehouse.locations.zoneCreateTitle') }}
            </el-button>
            <el-button @click="loadAll">{{ t('common.refresh') }}</el-button>
          </div>
          <el-table v-loading="loading" :data="zones" stripe style="width: 100%">
            <el-table-column prop="code" :label="t('warehouse.locations.zoneCode')" width="150" />
            <el-table-column prop="name" :label="t('warehouse.locations.zoneName')" min-width="160" />
            <el-table-column :label="t('warehouse.locations.zoneType')" width="130">
              <template #default="{ row }">{{ row.zone_type_label }}</template>
            </el-table-column>
            <el-table-column :label="t('warehouse.locations.capacity')" width="110" align="right">
              <template #default="{ row }">{{ row.capacity ?? '—' }}</template>
            </el-table-column>
            <el-table-column :label="t('warehouse.locations.sortOrder')" width="90" align="right">
              <template #default="{ row }">{{ row.sort_order }}</template>
            </el-table-column>
            <el-table-column :label="t('warehouse.locations.locationCount')" width="110" align="right">
              <template #default="{ row }">{{ row.location_count }}</template>
            </el-table-column>
            <el-table-column :label="t('warehouse.locations.enabled')" width="90" align="center">
              <template #default="{ row }">
                <el-tag :type="row.enabled ? 'success' : 'info'" size="small">
                  {{ row.enabled ? '✓' : '—' }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column :label="t('warehouse.warehouses.actions')" width="170" fixed="right">
              <template #default="{ row }">
                <el-button size="small" @click="openZoneEdit(row)">{{ t('warehouse.warehouses.edit') }}</el-button>
                <el-button size="small" type="danger" @click="removeZone(row)">
                  {{ t('warehouse.locations.delete') }}
                </el-button>
              </template>
            </el-table-column>
            <template #empty><el-empty :description="t('warehouse.locations.empty')" /></template>
          </el-table>
        </el-tab-pane>
      </el-tabs>
    </el-card>

    <!-- 库区表单 -->
    <el-dialog
      v-model="zoneDlg.open"
      :title="zoneDlg.id ? t('warehouse.locations.zoneEditTitle') : t('warehouse.locations.zoneCreateTitle')"
      width="520px"
      destroy-on-close
    >
      <el-form :model="zoneDlg.form" label-width="110px">
        <el-form-item :label="t('warehouse.locations.zoneCode')" required>
          <el-input v-model="zoneDlg.form.code" :disabled="!!zoneDlg.id" maxlength="32" />
        </el-form-item>
        <el-form-item :label="t('warehouse.locations.zoneName')" required>
          <el-input v-model="zoneDlg.form.name" maxlength="128" />
        </el-form-item>
        <el-form-item :label="t('warehouse.locations.zoneType')">
          <el-select v-model="zoneDlg.form.zone_type" style="width: 100%">
            <el-option
              v-for="zt in ZONE_TYPES"
              :key="zt.value"
              :label="t(`warehouse.locations.${zt.labelKey}`)"
              :value="zt.value"
            />
          </el-select>
        </el-form-item>
        <el-form-item :label="t('warehouse.locations.capacity')">
          <el-input-number v-model="zoneDlg.form.capacity" :min="0" :controls="false" style="width: 100%" />
          <div class="text-xs text-el-placeholder mt-1">{{ t('warehouse.locations.capacityHint') }}</div>
        </el-form-item>
        <el-form-item :label="t('warehouse.locations.sortOrder')">
          <el-input-number v-model="zoneDlg.form.sort_order" :min="0" style="width: 100%" />
        </el-form-item>
        <el-form-item :label="t('warehouse.locations.enabled')">
          <el-switch v-model="zoneDlg.form.enabled" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="zoneDlg.open = false">{{ t('warehouse.warehouses.cancel') }}</el-button>
        <el-button type="primary" :loading="zoneDlg.saving" @click="saveZone">
          {{ t('warehouse.warehouses.save') }}
        </el-button>
      </template>
    </el-dialog>

    <!-- 库位表单 -->
    <el-dialog
      v-model="locDlg.open"
      :title="t('warehouse.locations.tabLocations')"
      width="520px"
      destroy-on-close
    >
      <el-form :model="locDlg.form" label-width="110px">
        <el-form-item :label="t('warehouse.warehouses.code')" required>
          <el-input v-model="locDlg.form.code" :disabled="!!locDlg.id" maxlength="32" />
        </el-form-item>
        <el-form-item :label="t('warehouse.warehouses.name')" required>
          <el-input v-model="locDlg.form.name" maxlength="128" />
        </el-form-item>
        <el-form-item :label="t('warehouse.locations.zone')">
          <el-select v-model="locDlg.form.zone_id" clearable style="width: 100%">
            <el-option v-for="z in zones" :key="z.id" :label="`${z.code} ${z.name}`" :value="z.id" />
          </el-select>
        </el-form-item>
        <el-form-item :label="t('warehouse.locations.locationType')">
          <el-select v-model="locDlg.form.location_type" style="width: 100%">
            <el-option
              v-for="lt in LOCATION_TYPES"
              :key="lt.value"
              :label="t(`warehouse.locations.${lt.labelKey}`)"
              :value="lt.value"
            />
          </el-select>
        </el-form-item>
        <el-form-item :label="t('warehouse.locations.capacity')">
          <el-input-number v-model="locDlg.form.capacity" :min="0" :controls="false" style="width: 100%" />
          <div class="text-xs text-el-placeholder mt-1">{{ t('warehouse.locations.capacityHint') }}</div>
        </el-form-item>
        <el-form-item :label="t('warehouse.locations.isActive')">
          <el-switch v-model="locDlg.form.is_active" />
        </el-form-item>
        <el-form-item :label="t('warehouse.stocks.remark')">
          <el-input v-model="locDlg.form.remark" maxlength="255" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="locDlg.open = false">{{ t('warehouse.warehouses.cancel') }}</el-button>
        <el-button type="primary" :loading="locDlg.saving" @click="saveLocation">
          {{ t('warehouse.warehouses.save') }}
        </el-button>
      </template>
    </el-dialog>

    <!-- 库位库存 -->
    <el-drawer v-model="stockDrawer.open" :title="t('warehouse.locations.qtyOnHand')" size="60%">
      <div v-loading="stockDrawer.loading">
        <div v-if="stockDrawer.location" class="mb-3 text-sm">
          <span class="font-medium">{{ stockDrawer.location.code }}</span>
          <span class="ml-2 text-el-placeholder">{{ stockDrawer.location.name }}</span>
        </div>
        <el-table :data="stockDrawer.items" stripe>
          <el-table-column prop="batch_no" :label="t('warehouse.batches.batchNo')" width="170" />
          <el-table-column prop="sku_code" :label="t('warehouse.stocks.skuCode')" width="150" />
          <el-table-column prop="sku_name" :label="t('warehouse.stocks.skuName')" min-width="160" />
          <el-table-column prop="qty_on_hand" :label="t('warehouse.batches.qtyOnHand')" width="110" align="right" />
          <el-table-column prop="qty_reserved" :label="t('warehouse.batches.qtyReserved')" width="100" align="right" />
          <el-table-column prop="available" :label="t('warehouse.batches.available')" width="100" align="right" />
          <el-table-column prop="status" :label="t('warehouse.batches.status')" width="100" />
          <el-table-column prop="expiry_date" :label="t('warehouse.batches.expiryDate')" width="130" />
          <template #empty><el-empty :description="t('warehouse.batches.empty')" /></template>
        </el-table>
      </div>
    </el-drawer>
  </AdminPage>
</template>
