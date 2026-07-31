<script setup lang="ts">
import AdminPage from '@/components/admin/AdminPage.vue'
import { computed, onMounted, reactive, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { useAuthStore } from '@/stores/auth'
import { masterApi, type ProductOut } from '@/api/master'
import { http } from '@/utils/http'
import { openPrintWindow } from '@/utils/print'
import { productOptionLabel } from '@/utils/display'
import {
  productionApi,
  type CustomerContactIn,
  type CustomerContactOut,
  type CustomerOut,
  type CustomerTagOut,
  type OpportunityIn,
  type OpportunityOut,
  type OpportunityActivityOut,
  type OrderSkuOption,
} from '@/api/production'
import { orderSkuOptionLabel } from '@/utils/display'
import { useStatus } from '@/utils/status-maps'

const { t } = useI18n()
const { label: statusLabel } = useStatus('crm_opportunity')
const route = useRoute()
const router = useRouter()
const auth = useAuthStore()

const customerId = computed(() => Number(route.params.id))
const isAdmin = computed(() => Boolean(auth.me?.is_superuser))
const canManageCustomer = computed(() => auth.hasAnyPermission('customer.manage'))
const ownerSaving = ref(false)
const editOwnerUserId = ref<number | null>(null)

async function onPrint() {
  if (!customer.value) return
  const resp = await productionApi.printCustomer(customer.value.id, { template_code: 'customer_card' })
  const html = resp?.html || ''
  if (!html) return
  openPrintWindow(html, { title: `customer_${customer.value.id}`, autoPrint: true })
}

async function onExportPdf() {
  if (!customer.value) return
  const res = await productionApi.exportCustomerPdf(customer.value.id, { template_code: 'customer_card' })
  const blob = await http.request<Blob>({ url: `/files/${res.attachment_id}`, method: 'GET', params: { download: true }, responseType: 'blob' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = res.filename || `customer_${customer.value.id}.pdf`
  document.body.appendChild(a)
  a.click()
  a.remove()
  URL.revokeObjectURL(url)
}

const loading = ref(false)
const customer = ref<CustomerOut | null>(null)
const allTags = ref<CustomerTagOut[]>([])
const selectedTagIds = ref<number[]>([])
const tagsSaving = ref(false)

const users = ref<{ id: number; full_name: string | null; username: string }[]>([])

const activeTab = ref<'products' | 'contacts' | 'opps'>('products')

const allProducts = ref<ProductOut[]>([])
const selectedProductIds = ref<number[]>([])
const productsSaving = ref(false)
const productsLoading = ref(false)

const loginDlg = reactive({
  open: false,
  saving: false,
  login_username: '',
  login_password: '',
})

const contactsLoading = ref(false)
const contacts = ref<CustomerContactOut[]>([])
const contactsQuery = reactive({ include_inactive: false })

const contactDlg = reactive({
  open: false,
  saving: false,
  editingId: null as number | null,
  form: {
    name: '',
    phone: '',
    email: '',
    title: '',
    is_primary: false,
    is_active: true,
    remark: '',
  } as any,
})

const oppsLoading = ref(false)
const opps = ref<OpportunityOut[]>([])
const oppDlg = reactive({
  open: false,
  saving: false,
  editingId: null as number | null,
  form: {
    code: '',
    title: '',
    stage: 'prospecting',
    status: 'open',
    amount: null as number | null,
    probability: null as number | null,
    expected_close_date: null as string | null,
    owner_user_id: null as number | null,
    is_active: true,
    remark: '',
  } as any,
})

const actDrawer = reactive({
  open: false,
  loading: false,
  saving: false,
  opp: null as OpportunityOut | null,
  items: [] as OpportunityActivityOut[],
  form: { action_type: 'note', content: '', next_follow_up_at: null as string | null },
})

const convertDlg = reactive({
  open: false,
  saving: false,
  opp: null as OpportunityOut | null,
  due_date: null as string | null,
  remark: '',
  skus: [] as OrderSkuOption[],
  lines: [] as { sku_id: number | null; qty: number; remark: string }[],
})

function stageLabel(s: string) {
  const map: Record<string, string> = {
    prospecting: t('production.customers.stageProspecting'),
    qualified: t('production.customers.stageQualified'),
    quoted: t('production.customers.stageQuoted'),
    negotiation: t('production.customers.stageNegotiation'),
    won: t('production.customers.stageWon'),
    lost: t('production.customers.stageLost'),
  }
  return map[s] || s
}

function money(v: number | null) {
  if (v === null || typeof v !== 'number') return '-'
  return v.toFixed(2)
}

async function loadCustomer() {
  loading.value = true
  try {
    customer.value = await productionApi.getCustomer(customerId.value)
    editOwnerUserId.value = customer.value?.owner_user_id ?? null
    loginDlg.login_username = customer.value?.login_username || ''
    loginDlg.login_password = ''
  } finally {
    loading.value = false
  }
}

async function loadCustomerProducts() {
  productsLoading.value = true
  try {
    const res = await productionApi.getCustomerProducts(customerId.value)
    selectedProductIds.value = res.product_ids ?? []
  } finally {
    productsLoading.value = false
  }
}

async function loadAllProducts() {
  const res = await masterApi.listProducts({ offset: 0, limit: 200, include_inactive: false })
  allProducts.value = res.items ?? []
}

async function saveCustomerProducts() {
  productsSaving.value = true
  try {
    await productionApi.setCustomerProducts(customerId.value, selectedProductIds.value)
    ElMessage.success(t('production.customers.productsSaved'))
    await loadCustomer()
  } finally {
    productsSaving.value = false
  }
}

function openLoginDlg() {
  loginDlg.login_username = customer.value?.login_username || ''
  loginDlg.login_password = ''
  loginDlg.open = true
}

async function saveLogin() {
  if (!loginDlg.login_username.trim()) {
    ElMessage.warning(t('production.customers.pleaseInputLoginAccount'))
    return
  }
  if (!customer.value?.login_username && (!loginDlg.login_password || loginDlg.login_password.length < 6)) {
    ElMessage.warning(t('production.customers.passwordMinLength'))
    return
  }
  loginDlg.saving = true
  try {
    await productionApi.updateCustomer(customerId.value, {
      login_username: loginDlg.login_username.trim(),
      login_password: loginDlg.login_password || undefined,
    })
    loginDlg.open = false
    ElMessage.success(t('production.customers.loginAccountSaved'))
    await loadCustomer()
  } finally {
    loginDlg.saving = false
  }
}

async function loadTags() {
  const res = await productionApi.listCrmTags({ include_inactive: false, limit: 200 })
  allTags.value = res.items ?? []
  const current = await productionApi.getCustomerTags(customerId.value)
  selectedTagIds.value = (current.items ?? []).map(x => x.tag_id)
}

async function saveTags() {
  tagsSaving.value = true
  try {
    await productionApi.setCustomerTags(customerId.value, selectedTagIds.value)
    ElMessage.success(t('production.customers.tagsSaved'))
  } finally {
    tagsSaving.value = false
  }
}

async function saveOwner() {
  if (!customer.value) return
  ownerSaving.value = true
  try {
    await productionApi.updateCustomer(customerId.value, { owner_user_id: editOwnerUserId.value })
    ElMessage.success('负责人已更新')
    await loadCustomer()
  } finally {
    ownerSaving.value = false
  }
}

async function loadUsers() {
  const res = await productionApi.listUsers({ offset: 0, limit: 200, include_inactive: false })
  users.value = (res.items ?? []).map((x: any) => ({ id: x.id, full_name: x.full_name, username: x.username }))
}

async function loadContacts() {
  contactsLoading.value = true
  try {
    const res = await productionApi.listCustomerContacts(customerId.value, { ...contactsQuery })
    contacts.value = res.items ?? []
  } finally {
    contactsLoading.value = false
  }
}

function openCreateContact() {
  contactDlg.editingId = null
  contactDlg.form = { name: '', phone: '', email: '', title: '', is_primary: false, is_active: true, remark: '' }
  contactDlg.open = true
}

function openEditContact(row: CustomerContactOut) {
  contactDlg.editingId = row.id
  contactDlg.form = {
    name: row.name,
    phone: row.phone || '',
    email: row.email || '',
    title: row.title || '',
    is_primary: row.is_primary,
    is_active: row.is_active,
    remark: row.remark || '',
  }
  contactDlg.open = true
}

async function saveContact() {
  const data: CustomerContactIn = {
    name: String(contactDlg.form.name || '').trim(),
    phone: contactDlg.form.phone ? String(contactDlg.form.phone).trim() : null,
    email: contactDlg.form.email ? String(contactDlg.form.email).trim() : null,
    title: contactDlg.form.title ? String(contactDlg.form.title).trim() : null,
    is_primary: Boolean(contactDlg.form.is_primary),
    is_active: Boolean(contactDlg.form.is_active),
    remark: contactDlg.form.remark ? String(contactDlg.form.remark).trim() : null,
  }
  if (!data.name) {
    ElMessage.error(t('production.customers.pleaseInputContactName'))
    return
  }
  contactDlg.saving = true
  try {
    if (contactDlg.editingId) {
      await productionApi.updateCustomerContact(customerId.value, contactDlg.editingId, data)
      ElMessage.success('已保存')
    } else {
      await productionApi.createCustomerContact(customerId.value, data)
      ElMessage.success('已创建')
    }
    contactDlg.open = false
    loadContacts()
  } finally {
    contactDlg.saving = false
  }
}

async function disableContact(row: CustomerContactOut) {
  await productionApi.deleteCustomerContact(customerId.value, row.id)
  ElMessage.success(t('production.customers.disabled'))
  loadContacts()
}

async function loadOpps() {
  oppsLoading.value = true
  try {
    const res = await productionApi.listOpportunities(customerId.value, { include_inactive: true })
    opps.value = res.items ?? []
  } finally {
    oppsLoading.value = false
  }
}

function openCreateOpp() {
  oppDlg.editingId = null
  oppDlg.form = {
    code: '',
    title: '',
    stage: 'prospecting',
    status: 'open',
    amount: null,
    probability: null,
    expected_close_date: null,
    owner_user_id: null,
    is_active: true,
    remark: '',
  }
  oppDlg.open = true
}

function openEditOpp(row: OpportunityOut) {
  oppDlg.editingId = row.id
  oppDlg.form = {
    code: row.code,
    title: row.title,
    stage: row.stage,
    status: row.status,
    amount: row.amount,
    probability: row.probability,
    expected_close_date: row.expected_close_date,
    owner_user_id: row.owner_user_id,
    is_active: row.is_active,
    remark: row.remark || '',
  }
  oppDlg.open = true
}

async function saveOpp() {
  const data: OpportunityIn = {
    code: oppDlg.form.code ? String(oppDlg.form.code).trim() : null,
    title: String(oppDlg.form.title || '').trim(),
    stage: String(oppDlg.form.stage || 'prospecting'),
    status: String(oppDlg.form.status || 'open'),
    amount: oppDlg.form.amount === null ? null : Number(oppDlg.form.amount),
    probability: oppDlg.form.probability === null ? null : Number(oppDlg.form.probability),
    expected_close_date: oppDlg.form.expected_close_date || null,
    owner_user_id: oppDlg.form.owner_user_id || null,
    is_active: Boolean(oppDlg.form.is_active),
    remark: oppDlg.form.remark ? String(oppDlg.form.remark).trim() : null,
  }
  if (!data.title) {
    ElMessage.error(t('production.customers.pleaseInputOppTitle'))
    return
  }
  oppDlg.saving = true
  try {
    if (oppDlg.editingId) {
      await productionApi.updateOpportunity(customerId.value, oppDlg.editingId, data)
      ElMessage.success('已保存')
    } else {
      await productionApi.createOpportunity(customerId.value, data)
      ElMessage.success('已创建')
    }
    oppDlg.open = false
    loadOpps()
  } finally {
    oppDlg.saving = false
  }
}

async function disableOpp(row: OpportunityOut) {
  await productionApi.deleteOpportunity(customerId.value, row.id)
  ElMessage.success(t('production.customers.disabled'))
  loadOpps()
}

async function releaseOpp(row: OpportunityOut) {
  await productionApi.releaseCrmPublicPoolOpportunity(row.id)
  ElMessage.success(t('production.customers.releasedToPool'))
  loadOpps()
}

async function openActivities(row: OpportunityOut) {
  actDrawer.open = true
  actDrawer.opp = row
  actDrawer.form = { action_type: 'note', content: '', next_follow_up_at: null }
  actDrawer.loading = true
  try {
    const res = await productionApi.listOpportunityActivities(customerId.value, row.id)
    actDrawer.items = res.items ?? []
  } finally {
    actDrawer.loading = false
  }
}

async function addActivity() {
  if (!actDrawer.opp) return
  const content = String(actDrawer.form.content || '').trim()
  if (!content) {
    ElMessage.error(t('production.customers.pleaseInputFollowContent'))
    return
  }
  actDrawer.saving = true
  try {
    await productionApi.createOpportunityActivity(customerId.value, actDrawer.opp.id, {
      action_type: actDrawer.form.action_type,
      content,
      next_follow_up_at: actDrawer.form.next_follow_up_at || undefined,
    })
    actDrawer.form.content = ''
    const res = await productionApi.listOpportunityActivities(customerId.value, actDrawer.opp.id)
    actDrawer.items = res.items ?? []
    ElMessage.success(t('production.customers.recorded'))
  } finally {
    actDrawer.saving = false
  }
}

async function openConvertOrder(row: OpportunityOut) {
  convertDlg.opp = row
  convertDlg.due_date = row.expected_close_date
  convertDlg.remark = row.title
  convertDlg.lines = [{ sku_id: null, qty: 1, remark: '' }]
  const opts = await productionApi.fetchOrderFormOptions()
  convertDlg.skus = opts.skus || []
  convertDlg.open = true
}

async function submitConvertOrder() {
  if (!convertDlg.opp) return
  const items = convertDlg.lines
    .filter((row) => row.sku_id != null && Number(row.qty) > 0)
    .map((row, idx) => ({ line_no: idx + 1, sku_id: row.sku_id as number, qty: Number(row.qty), remark: row.remark || null }))
  if (!items.length) {
    ElMessage.warning('请添加至少一行 SKU')
    return
  }
  convertDlg.saving = true
  try {
    const res = await productionApi.convertOpportunityToOrder(customerId.value, convertDlg.opp.id, {
      due_date: convertDlg.due_date,
      remark: convertDlg.remark || undefined,
      items,
    })
    convertDlg.open = false
    ElMessage.success(`已转订单 ${res.order_code}`)
    loadOpps()
    router.push({ name: 'production-orders', query: { keyword: res.order_code } })
  } finally {
    convertDlg.saving = false
  }
}

onMounted(async () => {
  if (route.query.tab === 'opps') activeTab.value = 'opps'
  await loadCustomer()
  await loadAllProducts()
  await loadCustomerProducts()
  await loadUsers()
  await loadTags()
  await loadContacts()
  await loadOpps()
})
</script>


<template>
  <AdminPage :title="t('production.customers.detailTitle')">
    <el-card v-loading="loading" shadow="never">
      <div class="flex items-center justify-between gap-3 flex-wrap">
        <div>
          <div class="text-[16px] font-semibold">{{ t('production.customers.detailTitle') }}</div>
          <div class="text-xs text-zinc-500 mt-1" v-if="customer">{{ customer.code }} · {{ customer.name }}</div>
        </div>
        <div class="flex items-center gap-2">
          <el-button v-if="customer" type="primary" @click="onPrint">{{ t('production.customers.print') }}</el-button>
          <el-button v-if="customer" type="warning" @click="onExportPdf">{{ t('production.customers.exportPdf') }}</el-button>
          <el-button @click="router.back()">{{ t('production.common.back') }}</el-button>
        </div>
      </div>

      <el-descriptions class="mt-4" :column="3" border v-if="customer">
        <el-descriptions-item label="编码">{{ customer.code }}</el-descriptions-item>
        <el-descriptions-item label="名称">{{ customer.name }}</el-descriptions-item>
        <el-descriptions-item label="状态">
          <el-tag :type="customer.is_active ? 'success' : 'info'">{{ customer.is_active ? '启用' : '停用' }}</el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="负责人">
          <template v-if="canManageCustomer">
            <el-select v-model="editOwnerUserId" clearable filterable placeholder="选择负责人" style="width: 200px">
              <el-option v-for="u in users" :key="u.id" :label="u.full_name || u.username" :value="u.id" />
            </el-select>
            <el-button class="ml-2" size="small" type="primary" :loading="ownerSaving" @click="saveOwner">保存</el-button>
          </template>
          <span v-else>{{ customer.owner_name || '—' }}</span>
        </el-descriptions-item>
        <el-descriptions-item label="主联系人">{{ customer.contact_name || '-' }}</el-descriptions-item>
        <el-descriptions-item label="电话">{{ customer.contact_phone || '-' }}</el-descriptions-item>
        <el-descriptions-item label="地址">{{ customer.address || '-' }}</el-descriptions-item>
        <el-descriptions-item label="备注" :span="3">{{ customer.remark || '-' }}</el-descriptions-item>
        <el-descriptions-item label="H5 登录">
          <span v-if="customer.login_username">{{ customer.login_username }}</span>
          <el-tag v-else type="warning" size="small">未开通</el-tag>
          <el-button class="ml-2" size="small" link type="primary" @click="openLoginDlg">设置登录</el-button>
        </el-descriptions-item>
        <el-descriptions-item label="可下单产品">{{ customer.product_count ?? 0 }} 个（见下方 Tab）</el-descriptions-item>
        <el-descriptions-item label="客户标签" :span="3">
          <div class="flex items-center gap-2 flex-wrap">
            <el-select v-model="selectedTagIds" multiple filterable placeholder="选择标签" style="width: 520px">
              <el-option v-for="t in allTags" :key="t.id" :label="t.name" :value="t.id" />
            </el-select>
            <el-button type="primary" :loading="tagsSaving" @click="saveTags">{{ t('production.common.save') }}</el-button>
          </div>
        </el-descriptions-item>
      </el-descriptions>
    </el-card>

    <el-card shadow="never" class="mt-4">
      <el-tabs v-model="activeTab">
        <el-tab-pane label="可下单产品" name="products">
          <div v-loading="productsLoading" class="py-2">
            <p class="text-sm text-zinc-500 mb-3">
              仅勾选的产品/型号会在该客户 H5 下单页显示；未配置任何产品时客户无法下单。
            </p>
            <el-select
              v-model="selectedProductIds"
              multiple
              filterable
              placeholder="选择可下单产品"
              style="width: 100%"
            >
              <el-option
                v-for="p in allProducts"
                :key="p.id"
                :label="productOptionLabel(p)"
                :value="p.id"
              />
            </el-select>
            <div class="mt-3">
              <el-button type="primary" :loading="productsSaving" @click="saveCustomerProducts">保存产品范围</el-button>
            </div>
          </div>
        </el-tab-pane>
        <el-tab-pane label="联系人" name="contacts">
          <div class="flex items-center justify-between">
            <div class="text-sm text-zinc-500">{{ t('production.customers.contactList') }}</div>
            <div class="flex items-center gap-2">
              <el-switch v-model="contactsQuery.include_inactive" active-text="含停用" @change="loadContacts" />
              <el-button type="primary" @click="openCreateContact">{{ t('production.customers.addContact') }}</el-button>
            </div>
          </div>

          <div class="mt-4" v-loading="contactsLoading">
            <el-table class="hidden lg:block w-full" :data="contacts" border>
              <el-table-column prop="name" label="姓名" width="140" />
              <el-table-column prop="title" label="职位" width="140" />
              <el-table-column prop="phone" label="电话" width="160" />
              <el-table-column prop="email" label="邮箱" width="220" />
              <el-table-column label="主联系人" width="110">
                <template #default="{ row }">
                  <el-tag v-if="row.is_primary" type="success">是</el-tag>
                  <span v-else>-</span>
                </template>
              </el-table-column>
              <el-table-column label="状态" width="110">
                <template #default="{ row }">
                  <el-tag :type="row.is_active ? 'success' : 'info'">{{ row.is_active ? '启用' : '停用' }}</el-tag>
                </template>
              </el-table-column>
              <el-table-column prop="remark" label="备注" min-width="180" />
              <el-table-column label="操作" width="180">
                <template #default="{ row }">
                  <el-button size="small" @click="openEditContact(row)">{{ t('production.common.edit') }}</el-button>
                  <el-button size="small" type="danger" plain :disabled="!row.is_active" @click="disableContact(row)">{{ t('production.customers.statusDisabled') }}</el-button>
                </template>
              </el-table-column>
            </el-table>
            <div class="lg:hidden space-y-3">
              <div v-for="row in contacts" :key="row.id" class="admin-mobile-row">
                <div class="admin-mobile-row__head">
                  <div class="min-w-0">
                    <div class="font-semibold text-el-primary">{{ row.name }}</div>
                    <div class="text-xs text-el-placeholder">{{ row.title || '—' }} · {{ row.phone || '—' }}</div>
                  </div>
                  <el-tag v-if="row.is_primary" type="success" size="small">主</el-tag>
                </div>
                <dl class="admin-mobile-kv">
                  <dt>邮箱</dt>
                  <dd class="break-all">{{ row.email || '—' }}</dd>
                  <dt>状态</dt>
                  <dd>
                    <el-tag :type="row.is_active ? 'success' : 'info'" size="small">{{ row.is_active ? '启用' : '停用' }}</el-tag>
                  </dd>
                  <dt>备注</dt>
                  <dd class="text-left">{{ row.remark || '—' }}</dd>
                </dl>
                <div class="admin-mobile-actions">
                  <el-button size="small" @click="openEditContact(row)">{{ t('production.common.edit') }}</el-button>
                  <el-button size="small" type="danger" plain :disabled="!row.is_active" @click="disableContact(row)">{{ t('production.customers.statusDisabled') }}</el-button>
                </div>
              </div>
              <el-empty v-if="!contactsLoading && !contacts.length" description="暂无联系人" />
            </div>
          </div>
        </el-tab-pane>

        <el-tab-pane label="销售机会" name="opps">
          <div class="flex items-center justify-between">
            <div class="text-sm text-zinc-500">{{ t('production.customers.oppList') }}</div>
            <el-button type="primary" @click="openCreateOpp">{{ t('production.customers.addOpp') }}</el-button>
          </div>

          <div class="mt-4" v-loading="oppsLoading">
            <el-table class="hidden lg:block w-full" :data="opps" border>
              <el-table-column prop="code" label="编号" width="180" />
              <el-table-column prop="title" label="标题" min-width="240" />
              <el-table-column label="阶段" width="120">
                <template #default="{ row }">{{ stageLabel(row.stage) }}</template>
              </el-table-column>
              <el-table-column label="状态" width="110">
                <template #default="{ row }">
                  <el-tag :type="row.status === 'won' ? 'success' : row.status === 'lost' ? 'danger' : 'info'">{{ statusLabel(row.status) }}</el-tag>
                </template>
              </el-table-column>
              <el-table-column label="金额" width="130">
                <template #default="{ row }">¥{{ money(row.amount) }}</template>
              </el-table-column>
              <el-table-column prop="probability" label="概率%" width="90" />
              <el-table-column prop="expected_close_date" label="预计成交" width="120" />
              <el-table-column prop="owner_name" label="负责人" width="140" />
              <el-table-column label="状态" width="110">
                <template #default="{ row }">
                  <el-tag :type="row.is_active ? 'success' : 'info'">{{ row.is_active ? '启用' : '停用' }}</el-tag>
                </template>
              </el-table-column>
              <el-table-column label="操作" width="260">
                <template #default="{ row }">
                  <el-button size="small" @click="openEditOpp(row)">{{ t('production.common.edit') }}</el-button>
                  <el-button size="small" type="primary" plain @click="openActivities(row)">{{ t('production.customers.follow') }}</el-button>
                  <el-button v-if="row.status === 'open' && !row.converted_order_id" size="small" type="success" plain @click="openConvertOrder(row)">{{ t('production.customers.convertOrder') }}</el-button>
                  <el-button v-if="isAdmin && row.owner_user_id" size="small" type="warning" plain @click="releaseOpp(row)">{{ t('production.customers.release') }}</el-button>
                  <el-button size="small" type="danger" plain :disabled="!row.is_active" @click="disableOpp(row)">{{ t('production.customers.statusDisabled') }}</el-button>
                </template>
              </el-table-column>
            </el-table>
            <div class="lg:hidden space-y-3">
              <div v-for="row in opps" :key="row.id" class="admin-mobile-row">
                <div class="admin-mobile-row__head">
                  <div class="min-w-0">
                    <div class="font-semibold text-el-primary">{{ row.title }}</div>
                    <div class="text-xs text-el-placeholder">{{ row.code }} · {{ stageLabel(row.stage) }}</div>
                  </div>
                  <el-tag :type="row.status === 'won' ? 'success' : row.status === 'lost' ? 'danger' : 'info'" size="small">{{ statusLabel(row.status) }}</el-tag>
                </div>
                <dl class="admin-mobile-kv">
                  <dt>金额</dt>
                  <dd>¥{{ money(row.amount) }}</dd>
                  <dt>概率</dt>
                  <dd>{{ row.probability ?? '—' }}%</dd>
                  <dt>预计</dt>
                  <dd>{{ row.expected_close_date || '—' }}</dd>
                  <dt>负责人</dt>
                  <dd>{{ row.owner_name || '—' }}</dd>
                  <dt>{{ t('production.customers.statusEnabled') }}</dt>
                  <dd>
                    <el-tag :type="row.is_active ? 'success' : 'info'" size="small">{{ row.is_active ? '启用' : '停用' }}</el-tag>
                  </dd>
                </dl>
                <div class="admin-mobile-actions">
                  <el-button size="small" @click="openEditOpp(row)">{{ t('production.common.edit') }}</el-button>
                  <el-button size="small" type="primary" plain @click="openActivities(row)">{{ t('production.customers.follow') }}</el-button>
                  <el-button v-if="row.status === 'open' && !row.converted_order_id" size="small" type="success" plain @click="openConvertOrder(row)">{{ t('production.customers.convertOrder') }}</el-button>
                  <el-button v-if="isAdmin && row.owner_user_id" size="small" type="warning" plain @click="releaseOpp(row)">{{ t('production.customers.release') }}</el-button>
                  <el-button size="small" type="danger" plain :disabled="!row.is_active" @click="disableOpp(row)">{{ t('production.customers.statusDisabled') }}</el-button>
                </div>
              </div>
              <el-empty v-if="!oppsLoading && !opps.length" description="暂无机会" />
            </div>
          </div>
        </el-tab-pane>
      </el-tabs>
    </el-card>
    <template #extra>
<el-dialog v-model="loginDlg.open" title="客户 H5 登录账号" width="480px" destroy-on-close>
    <el-form label-width="90px">
      <el-form-item label="登录账号" required>
        <el-input v-model="loginDlg.login_username" placeholder="H5 登录用户名" />
      </el-form-item>
      <el-form-item :label="customer?.login_username ? '重置密码' : '登录密码'">
        <el-input v-model="loginDlg.login_password" type="password" show-password placeholder="至少 6 位，留空则不修改" />
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="loginDlg.open = false">{{ t('production.common.cancel') }}</el-button>
      <el-button type="primary" :loading="loginDlg.saving" @click="saveLogin">{{ t('production.common.save') }}</el-button>
    </template>
  </el-dialog>

  <el-dialog v-model="contactDlg.open" :title="contactDlg.editingId ? '编辑联系人' : '新增联系人'" width="520px" destroy-on-close>
    <el-form :model="contactDlg.form" label-width="90px">
      <el-form-item label="姓名"><el-input v-model="contactDlg.form.name" /></el-form-item>
      <el-form-item label="电话"><el-input v-model="contactDlg.form.phone" /></el-form-item>
      <el-form-item label="邮箱"><el-input v-model="contactDlg.form.email" /></el-form-item>
      <el-form-item label="职位"><el-input v-model="contactDlg.form.title" /></el-form-item>
      <el-form-item label="主联系人"><el-switch v-model="contactDlg.form.is_primary" /></el-form-item>
      <el-form-item label="启用"><el-switch v-model="contactDlg.form.is_active" /></el-form-item>
      <el-form-item label="备注"><el-input v-model="contactDlg.form.remark" type="textarea" :rows="3" /></el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="contactDlg.open = false">{{ t('production.common.cancel') }}</el-button>
      <el-button type="primary" :loading="contactDlg.saving" @click="saveContact">{{ t('production.common.save') }}</el-button>
    </template>
  </el-dialog>

  <el-dialog v-model="oppDlg.open" :title="oppDlg.editingId ? '编辑销售机会' : '新增销售机会'" width="640px" destroy-on-close>
    <el-form :model="oppDlg.form" label-width="100px">
      <el-form-item label="编号"><el-input v-model="oppDlg.form.code" placeholder="留空自动生成" /></el-form-item>
      <el-form-item label="标题"><el-input v-model="oppDlg.form.title" /></el-form-item>
      <el-form-item label="阶段">
        <el-select v-model="oppDlg.form.stage" style="width: 220px">
          <el-option label="线索" value="prospecting" />
          <el-option label="已评估" value="qualified" />
          <el-option label="已报价" value="quoted" />
          <el-option label="谈判中" value="negotiation" />
          <el-option label="赢单" value="won" />
          <el-option label="输单" value="lost" />
        </el-select>
      </el-form-item>
      <el-form-item label="状态">
        <el-select v-model="oppDlg.form.status" style="width: 220px">
          <el-option label="进行中" value="open" />
          <el-option label="赢单" value="won" />
          <el-option label="输单" value="lost" />
        </el-select>
      </el-form-item>
      <el-form-item label="金额"><el-input-number v-model="oppDlg.form.amount" :min="0" :controls="false" style="width: 220px" /></el-form-item>
      <el-form-item label="概率%"><el-input-number v-model="oppDlg.form.probability" :min="0" :max="100" :controls="false" style="width: 220px" /></el-form-item>
      <el-form-item label="预计成交"><el-date-picker v-model="oppDlg.form.expected_close_date" type="date" value-format="YYYY-MM-DD" style="width: 220px" /></el-form-item>
      <el-form-item label="负责人">
        <el-select v-model="oppDlg.form.owner_user_id" clearable filterable placeholder="选择负责人" style="width: 220px">
          <el-option v-for="u in users" :key="u.id" :label="u.full_name || u.username" :value="u.id" />
        </el-select>
      </el-form-item>
      <el-form-item label="启用"><el-switch v-model="oppDlg.form.is_active" /></el-form-item>
      <el-form-item label="备注"><el-input v-model="oppDlg.form.remark" type="textarea" :rows="3" /></el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="oppDlg.open = false">{{ t('production.common.cancel') }}</el-button>
      <el-button type="primary" :loading="oppDlg.saving" @click="saveOpp">{{ t('production.common.save') }}</el-button>
    </template>
  </el-dialog>

  <el-drawer v-model="actDrawer.open" title="跟进记录" size="560px">
    <div v-if="actDrawer.opp" class="text-sm text-zinc-500 mb-2">{{ actDrawer.opp.code }} · {{ actDrawer.opp.title }}</div>
    <el-form :model="actDrawer.form" label-width="70px">
      <el-form-item label="类型">
        <el-select v-model="actDrawer.form.action_type" style="width: 140px">
          <el-option label="备注" value="note" />
          <el-option label="电话" value="call" />
          <el-option label="拜访" value="visit" />
        </el-select>
      </el-form-item>
      <el-form-item label="内容">
        <el-input v-model="actDrawer.form.content" type="textarea" :rows="3" />
      </el-form-item>
      <el-form-item label="下次跟进">
        <el-date-picker v-model="actDrawer.form.next_follow_up_at" type="datetime" value-format="YYYY-MM-DDTHH:mm:ss" style="width: 100%" />
      </el-form-item>
      <el-form-item>
        <el-button type="primary" :loading="actDrawer.saving" @click="addActivity">{{ t('production.common.create') }}</el-button>
      </el-form-item>
    </el-form>

    <el-divider />

    <div v-loading="actDrawer.loading">
      <el-table class="hidden lg:block w-full" :data="actDrawer.items" border>
        <el-table-column prop="created_at" label="时间" width="170" />
        <el-table-column prop="action_type" label="类型" width="80" />
        <el-table-column prop="created_by_name" label="记录人" width="100" />
        <el-table-column prop="content" label="内容" min-width="220" />
      </el-table>
      <div class="lg:hidden space-y-3">
        <div v-for="(row, idx) in actDrawer.items" :key="idx" class="admin-mobile-row">
          <div class="admin-mobile-row__head">
            <span class="text-xs text-el-placeholder">{{ row.created_at }}</span>
            <el-tag size="small">{{ row.action_type }}</el-tag>
          </div>
          <div class="text-xs text-el-placeholder">记录人：{{ row.created_by_name || '—' }}</div>
          <p class="text-sm text-el-regular m-0 mt-1">{{ row.content }}</p>
        </div>
        <el-empty v-if="!actDrawer.loading && !actDrawer.items.length" description="暂无跟进" />
      </div>
    </div>
  </el-drawer>

  <el-dialog v-model="convertDlg.open" :title="t('production.customers.convertOrder')" width="640px" destroy-on-close>
    <el-form label-width="80px">
      <el-form-item label="交期">
        <el-date-picker v-model="convertDlg.due_date" type="date" value-format="YYYY-MM-DD" style="width: 100%" />
      </el-form-item>
      <el-form-item label="备注">
        <el-input v-model="convertDlg.remark" type="textarea" :rows="2" />
      </el-form-item>
      <el-form-item label="明细">
        <div class="space-y-2 w-full">
          <div v-for="(row, idx) in convertDlg.lines" :key="idx" class="flex gap-2 items-center">
            <el-select v-model="row.sku_id" filterable placeholder="SKU" style="flex: 1">
              <el-option v-for="s in convertDlg.skus" :key="s.id" :label="orderSkuOptionLabel(s)" :value="s.id" />
            </el-select>
            <el-input-number v-model="row.qty" :min="1" style="width: 120px" />
            <el-button v-if="convertDlg.lines.length > 1" type="danger" link @click="convertDlg.lines.splice(idx, 1)">删</el-button>
          </div>
          <el-button link type="primary" @click="convertDlg.lines.push({ sku_id: null, qty: 1, remark: '' })">+ 添加行</el-button>
        </div>
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="convertDlg.open = false">{{ t('production.common.cancel') }}</el-button>
      <el-button type="primary" :loading="convertDlg.saving" @click="submitConvertOrder">{{ t('production.customers.convertOrder') }}</el-button>
    </template>
  </el-dialog>
    </template>
  </AdminPage>
</template>
