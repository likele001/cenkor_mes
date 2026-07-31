<template>
  <AdminPage :title="t('master.processRoutes.title')">
          <template #actions>
      <div class="flex items-center gap-2 flex-wrap justify-end">
          <el-select v-model="query.product_id" clearable filterable :placeholder="t('master.processRoutes.product')" style="width: 220px" @change="reload(true)">
            <el-option v-for="p in products" :key="p.id" :label="productOptionLabel(p)" :value="p.id" />
          </el-select>
          <el-switch v-model="query.include_inactive" :active-text="t('master.processRoutes.includeDisabled')" @change="reload(true)" />
          <el-button type="primary" @click="openCreate">{{ t('master.processRoutes.add') }}</el-button>
        </div>
    </template>


      <div class="mt-4" v-loading="loading">
        <el-table class="hidden lg:block w-full" :data="items" border>
          <el-table-column prop="id" :label="t('master.common.id')" width="90" />
          <el-table-column :label="t('master.processRoutes.product')" width="260">
            <template #default="{ row }">
              <span>{{ productLabel(row.product_id) }}</span>
            </template>
          </el-table-column>
          <el-table-column prop="name" :label="t('master.processRoutes.name')" width="220" />
          <el-table-column :label="t('master.processRoutes.isDefault')" width="120">
            <template #default="{ row }">
              <el-tag :type="row.is_default ? 'success' : 'info'">{{ row.is_default ? t('master.processRoutes.yes') : t('master.processRoutes.no') }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column :label="t('master.processRoutes.steps')">
            <template #default="{ row }">
              <span class="text-[12px] text-gray-700">{{ stepsLabel(row.steps) }}</span>
            </template>
          </el-table-column>
          <el-table-column :label="t('master.processRoutes.status')" width="120">
            <template #default="{ row }">
              <el-tag :type="row.is_active ? 'success' : 'info'">{{ row.is_active ? t('master.processRoutes.enabled') : t('master.processRoutes.disabled') }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column :label="t('master.processRoutes.operation')" width="220" fixed="right">
            <template #default="{ row }">
              <el-button size="small" @click="openEdit(row)">{{ t('master.processRoutes.edit') }}</el-button>
              <el-popconfirm :title="t('master.processRoutes.confirmDisable')" @confirm="onDisable(row)">
                <template #reference>
                  <el-button size="small" type="danger" :disabled="!row.is_active">{{ t('master.processRoutes.disable') }}</el-button>
                </template>
              </el-popconfirm>
            </template>
          </el-table-column>
        </el-table>

        <div class="lg:hidden space-y-3">
          <div v-for="row in items" :key="row.id" class="admin-mobile-row">
            <div class="admin-mobile-row__head">
              <div class="min-w-0">
                <div class="font-semibold text-el-primary">{{ row.name }}</div>
                <div class="text-xs text-el-placeholder">#{{ row.id }} · {{ productLabel(row.product_id) }}</div>
              </div>
              <div class="flex flex-col items-end gap-1">
                <el-tag :type="row.is_active ? 'success' : 'info'" size="small">{{ row.is_active ? t('master.processRoutes.enabled') : t('master.processRoutes.disabled') }}</el-tag>
                <el-tag v-if="row.is_default" type="success" size="small">{{ t('master.processRoutes.isDefault') }}</el-tag>
              </div>
            </div>
            <div class="text-xs text-el-regular leading-snug">{{ stepsLabel(row.steps) }}</div>
            <div class="admin-mobile-actions">
              <el-button size="small" @click="openEdit(row)">{{ t('master.processRoutes.edit') }}</el-button>
              <el-popconfirm :title="t('master.processRoutes.confirmDisable')" @confirm="onDisable(row)">
                <template #reference>
                  <el-button size="small" type="danger" :disabled="!row.is_active">{{ t('master.processRoutes.disable') }}</el-button>
                </template>
              </el-popconfirm>
            </div>
          </div>
          <el-empty v-if="!loading && !items.length" :description="t('master.processRoutes.noData')" />
        </div>
      </div>

      <div class="mt-4 flex justify-end">
        <el-pagination
          background
          layout="prev, pager, next"
          :page-size="query.limit"
          :total="fakeTotal"
          :current-page="page"
          @current-change="onPageChange"
        />
      </div>
    <template #extra>
    <el-dialog v-model="dlg.open" :title="dlg.id ? t('master.processRoutes.editTitle') : t('master.processRoutes.addTitle')" width="900px" destroy-on-close>
      <el-form ref="formRef" :model="dlg.form" :rules="rules" label-width="100px">
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item :label="t('master.processRoutes.product')" prop="product_id">
              <el-select v-model="dlg.form.product_id" filterable style="width: 100%">
                <el-option v-for="p in products" :key="p.id" :label="productOptionLabel(p)" :value="p.id" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item :label="t('master.processRoutes.name')" prop="name">
              <el-input v-model="dlg.form.name" />
            </el-form-item>
          </el-col>
        </el-row>

        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item :label="t('master.processRoutes.isDefault')" prop="is_default">
              <el-switch v-model="dlg.form.is_default" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item :label="t('master.processRoutes.enable')" prop="is_active">
              <el-switch v-model="dlg.form.is_active" />
            </el-form-item>
          </el-col>
        </el-row>

        <el-form-item :label="t('master.processRoutes.steps')" prop="steps">
          <div class="w-full">
            <div class="flex justify-end mb-2">
              <el-button size="small" @click="addStep">{{ t('master.processRoutes.addStep') }}</el-button>
            </div>
            <el-table :data="dlg.form.steps" border>
              <el-table-column :label="t('master.processRoutes.seq')" width="140">
                <template #default="{ row }">
                  <el-input-number v-model="row.seq" :min="1" :controls="false" />
                </template>
              </el-table-column>
              <el-table-column :label="t('master.processRoutes.process')">
                <template #default="{ row }">
                  <el-select v-model="row.process_id" filterable style="width: 100%">
                    <el-option v-for="p in processes" :key="p.id" :label="processOptionLabel(p)" :value="p.id" />
                  </el-select>
                </template>
              </el-table-column>
              <el-table-column :label="t('master.processRoutes.operation')" width="120">
                <template #default="{ $index }">
                  <el-button size="small" type="danger" @click="removeStep($index)">{{ t('master.processRoutes.delete') }}</el-button>
                </template>
              </el-table-column>
            </el-table>
          </div>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dlg.open = false">{{ t('master.common.cancel') }}</el-button>
        <el-button type="primary" :loading="dlg.saving" @click="onSave">{{ t('master.common.save') }}</el-button>
      </template>
    </el-dialog>
    </template>
  </AdminPage>
</template>

<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import AdminPage from '@/components/admin/AdminPage.vue'
import { computed, onMounted, reactive, ref } from 'vue'
import type { FormInstance, FormRules } from 'element-plus'
import { masterApi, type ProcessOut, type ProcessRouteOut, type ProductOut } from '@/api/master'
import { processOptionLabel, productOptionLabel } from '@/utils/display'

const { t } = useI18n()

type StepIn = { seq: number; process_id: number | null }

const loading = ref(false)
const items = ref<ProcessRouteOut[]>([])
const products = ref<ProductOut[]>([])
const processes = ref<ProcessOut[]>([])
const query = reactive({ product_id: null as number | null, offset: 0, limit: 50, include_inactive: false })

const page = computed(() => Math.floor(query.offset / query.limit) + 1)
const fakeTotal = computed(() => query.offset + items.value.length + (items.value.length === query.limit ? query.limit : 0))

const dlg = reactive({
  open: false,
  id: null as number | null,
  saving: false,
  form: { product_id: null as number | null, name: '', is_default: false, is_active: true, steps: [] as StepIn[] },
})

const formRef = ref<FormInstance>()

const rules: FormRules = {
  product_id: [{ required: true, message: t('master.processRoutes.pleaseSelectProduct'), trigger: 'change' }],
  name: [{ required: true, message: t('master.processRoutes.pleaseInputName'), trigger: 'blur' }],
  steps: [
    {
      validator: (_: any, v: StepIn[], cb: any) => {
        if (!v || v.length === 0) return cb(new Error(t('master.processRoutes.atLeastOneStep')))
        const seqs = v.map((x) => x.seq)
        if (seqs.some((x) => !x || x <= 0)) return cb(new Error(t('master.processRoutes.stepSeqGtZero')))
        const uniq = new Set(seqs)
        if (uniq.size !== seqs.length) return cb(new Error(t('master.processRoutes.stepSeqNoDuplicate')))
        if (v.some((x) => !x.process_id)) return cb(new Error(t('master.processRoutes.pleaseSelectStepProcess')))
        return cb()
      },
      trigger: 'change',
    },
  ],
}

function productLabel(productId: number) {
  const p = products.value.find((x) => x.id === productId)
  return p ? productOptionLabel(p) : `${productId}`
}

function stepsLabel(steps: any[]) {
  if (!steps || steps.length === 0) return '-'
  const m = new Map(processes.value.map((x) => [x.id, processOptionLabel(x)]))
  return [...steps]
    .sort((a, b) => a.seq - b.seq)
    .map((s) => `${s.seq}.${m.get(s.process_id) || s.process_id}`)
    .join(' → ')
}

async function loadOptions() {
  const [p, proc] = await Promise.all([
    masterApi.listProducts({ offset: 0, limit: 200, include_inactive: true }),
    masterApi.listProcesses({ offset: 0, limit: 200, include_inactive: true }),
  ])
  products.value = p.items
  processes.value = proc.items
}

async function reload(reset = false) {
  if (reset) query.offset = 0
  loading.value = true
  try {
    const res = await masterApi.listRoutes({ ...query })
    items.value = res.items
  } finally {
    loading.value = false
  }
}

function onPageChange(p: number) {
  query.offset = (p - 1) * query.limit
  reload(false)
}

function openCreate() {
  dlg.id = null
  dlg.form = { product_id: query.product_id, name: '', is_default: false, is_active: true, steps: [{ seq: 1, process_id: null }] }
  dlg.open = true
}

function openEdit(row: ProcessRouteOut) {
  dlg.id = row.id
  dlg.form = {
    product_id: row.product_id,
    name: row.name,
    is_default: row.is_default,
    is_active: row.is_active,
    steps: (row.steps || []).map((s) => ({ seq: s.seq, process_id: s.process_id })),
  }
  if (dlg.form.steps.length === 0) dlg.form.steps = [{ seq: 1, process_id: null }]
  dlg.open = true
}

function addStep() {
  const seqs = dlg.form.steps.map((x) => x.seq).sort((a, b) => a - b)
  const nextSeq = ((seqs.length ? seqs[seqs.length - 1] : 0) || 0) + 1
  dlg.form.steps.push({ seq: nextSeq, process_id: null })
}

function removeStep(idx: number) {
  dlg.form.steps.splice(idx, 1)
}

async function onSave() {
  const ok = await formRef.value?.validate().catch(() => false)
  if (!ok) return
  dlg.saving = true
  try {
    const payload = {
      product_id: dlg.form.product_id,
      name: dlg.form.name,
      is_default: dlg.form.is_default,
      is_active: dlg.form.is_active,
      steps: dlg.form.steps.map((x) => ({ seq: x.seq, process_id: x.process_id })),
    }
    if (!dlg.id) await masterApi.createRoute(payload)
    else await masterApi.updateRoute(dlg.id, payload)
    dlg.open = false
    await reload(false)
  } finally {
    dlg.saving = false
  }
}

async function onDisable(row: ProcessRouteOut) {
  await masterApi.disableRoute(row.id)
  await reload(false)
}

onMounted(async () => {
  await loadOptions()
  await reload(true)
})
</script>
