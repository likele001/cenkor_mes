import { computed, reactive, ref } from 'vue'
import { crudCreate, crudGet, crudList, crudRemove, crudUpdate } from '@/api/admin/crudHttp'
import type { CrudField, CrudSchema } from '@/types/adminCrud'
import { getCrudSchema } from '@/constants/adminCrudSchemas'
import { usePermission } from '@/composables/usePermission'

type OptionMap = Record<string, { label: string; value: string | number }[]>

export function useAdminCrudPage(schemaKey: string) {
  const schema = getCrudSchema(schemaKey)
  const { requirePermission, hasPermission } = usePermission()

  const items = ref<Record<string, unknown>[]>([])
  const loading = ref(false)
  const keyword = ref('')
  const formVisible = ref(false)
  const formMode = ref<'create' | 'edit'>('create')
  const saving = ref(false)
  const editingId = ref<number | string | null>(null)
  const form = reactive<Record<string, unknown>>({})
  const optionMap = ref<OptionMap>({})

  const canWrite = computed(() => !schema.readonly && hasPermission(schema.permission))
  const canCreate = computed(() => canWrite.value && !!schema.createPath)
  const canEdit = computed(() => canWrite.value && !schema.createOnly && !!schema.updatePath)

  function defaultFormValues(): Record<string, unknown> {
    const v: Record<string, unknown> = {}
    for (const f of schema.fields) {
      if (f.type === 'switch') v[f.key] = true
      else if (f.type === 'number') v[f.key] = undefined
      else if (f.key === 'scope') v[f.key] = 'sku'
      else if (f.key === 'template_type') v[f.key] = 'html'
      else v[f.key] = ''
    }
    return v
  }

  async function loadRefOptions(field: CrudField) {
    if (!field.refList || optionMap.value[field.key]?.length) return
    try {
      const rows = (await crudList(field.refList.path, { limit: 200 })) as Record<string, unknown>[]
      const labelKeys = field.refList.labelKeys || ['name', 'code']
      const valueKey = field.refList.valueKey || 'id'
      optionMap.value[field.key] = rows.map((row) => ({
        value: row[valueKey] as string | number,
        label: labelKeys.map((k) => row[k]).filter(Boolean).join(' · ') || String(row[valueKey]),
      }))
    } catch {
      optionMap.value[field.key] = []
    }
  }

  async function reload() {
    if (!requirePermission(schema.permission)) return
    loading.value = true
    try {
      const params: Record<string, unknown> = { limit: 100 }
      if (keyword.value.trim() && schema.keywordParam !== '') {
        params.keyword = keyword.value.trim()
      }
      const rows = await crudList(schema.listPath, params)
      items.value = rows as Record<string, unknown>[]
    } catch {
      items.value = []
    } finally {
      loading.value = false
    }
  }

  function visibleFields(mode: 'create' | 'edit') {
    return schema.fields.filter((f) => {
      if (f.miniappExclude) return false
      if (mode === 'create' && f.editOnly) return false
      if (mode === 'edit' && f.createOnly) return false
      if (mode === 'create' && f.hiddenOnCreate) return false
      return true
    })
  }

  async function openCreate() {
    if (!canCreate.value) return
    formMode.value = 'create'
    editingId.value = null
    Object.assign(form, defaultFormValues())
    for (const f of schema.fields) {
      if (f.refList) await loadRefOptions(f)
    }
    formVisible.value = true
  }

  async function openEdit(row: Record<string, unknown>) {
    if (!canEdit.value) {
      if (schema.createOnly) {
        uni.showToast({ title: '该模块仅支持新增，详情请在列表查看', icon: 'none' })
      }
      return
    }
    formMode.value = 'edit'
    editingId.value = row.id as number | string
    Object.assign(form, defaultFormValues())
    for (const f of schema.fields) {
      if (f.refList) await loadRefOptions(f)
    }
    try {
      if (schema.getPath && editingId.value != null) {
        const detail = await crudGet(schema.getPath(editingId.value))
        Object.assign(form, schema.mapRecordToForm ? schema.mapRecordToForm(detail) : detail)
      } else {
        Object.assign(form, schema.mapRecordToForm ? schema.mapRecordToForm(row) : row)
      }
    } catch {
      Object.assign(form, row)
    }
    formVisible.value = true
  }

  function closeForm() {
    formVisible.value = false
  }

  function validate(): boolean {
    for (const f of visibleFields(formMode.value)) {
      if (!f.required) continue
      const v = form[f.key]
      if (v === undefined || v === null || v === '') {
        uni.showToast({ title: `请填写${f.label}`, icon: 'none' })
        return false
      }
    }
    return true
  }

  function buildPayload(): Record<string, unknown> {
    const payload: Record<string, unknown> = {}
    for (const f of visibleFields(formMode.value)) {
      let v = form[f.key]
      if (f.type === 'number' && v !== '' && v != null) v = Number(v)
      if (v === '') v = f.type === 'number' ? null : null
      if (v !== undefined) payload[f.key] = v
    }
    return schema.beforeSubmit ? schema.beforeSubmit(payload, formMode.value) : payload
  }

  async function submitForm() {
    if (!validate()) return
    saving.value = true
    try {
      const payload = buildPayload()
      if (formMode.value === 'create') {
        if (!schema.createPath) throw new Error('不支持新增')
        await crudCreate(schema.createPath, payload)
        uni.showToast({ title: '新增成功', icon: 'success' })
      } else if (editingId.value != null && schema.updatePath) {
        await crudUpdate(schema.updatePath(editingId.value), payload, schema.updateAsQuery)
        uni.showToast({ title: '保存成功', icon: 'success' })
      }
      formVisible.value = false
      await reload()
    } catch {
      /* toast in request */
    } finally {
      saving.value = false
    }
  }

  function confirmDelete(row: Record<string, unknown>) {
    if (!canEdit.value || !schema.deletePath) return
    const id = row.id as number | string
    uni.showModal({
      title: schema.deleteLabel || '删除',
      content: `确定${schema.deleteLabel || '删除'}「${schema.listTitle(row)}」？`,
      success: async (res) => {
        if (!res.confirm) return
        try {
          await crudRemove(schema.deletePath!(id))
          uni.showToast({ title: '操作成功', icon: 'success' })
          await reload()
        } catch {
          /* handled */
        }
      },
    })
  }

  function onSelect(row: Record<string, unknown>) {
    if (schema.readonly) {
      uni.showModal({
        title: schema.listTitle(row),
        content: schema.listSub?.(row) || JSON.stringify(row, null, 2).slice(0, 500),
        showCancel: false,
      })
      return
    }
    openEdit(row)
  }

  return {
    schema,
    items,
    loading,
    keyword,
    formVisible,
    formMode,
    saving,
    form,
    optionMap,
    canWrite,
    canCreate,
    canEdit,
    visibleFields,
    reload,
    openCreate,
    openEdit,
    closeForm,
    submitForm,
    confirmDelete,
    onSelect,
    loadRefOptions,
  }
}
