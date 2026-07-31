import type { CrudField, CrudSchema } from '@/types/adminCrud'

const activeSwitch: CrudField = { key: 'is_active', label: '启用', type: 'switch' }
const codeField: CrudField = { key: 'code', label: '编码', placeholder: '留空自动生成' }
const nameField: CrudField = { key: 'name', label: '名称', required: true }

function std(path: string, cfg: Omit<CrudSchema, 'listPath' | 'createPath' | 'updatePath' | 'deletePath' | 'getPath'>): CrudSchema {
  return {
    ...cfg,
    listPath: path,
    createPath: path,
    getPath: (id) => `${path}/${id}`,
    updatePath: (id) => `${path}/${id}`,
    deletePath: (id) => `${path}/${id}`,
    deleteLabel: '停用',
  }
}

function titleCodeName(prefix = '') {
  return {
    listTitle: (item: Record<string, unknown>) =>
      String(item.display_name || item.name || item.code || item.title || `${prefix}${item.id}`),
    listSub: (item: Record<string, unknown>) => {
      const parts = [item.code, item.status, item.is_active === false ? '已停用' : ''].filter(Boolean)
      return parts.join(' · ') || '点击查看/编辑'
    },
  }
}

export const ADMIN_CRUD_SCHEMAS: Record<string, CrudSchema> = {
  departments: std('/admin/system/departments', {
    key: 'departments',
    title: '部门管理',
    permission: 'department.manage',
    fields: [codeField, nameField, { key: 'parent_id', label: '上级部门ID', type: 'number', placeholder: '可选' }, activeSwitch],
    ...titleCodeName(),
  }),

  products: std('/admin/master/products', {
    key: 'products',
    title: '产品管理',
    permission: 'product.manage',
    fields: [
      codeField,
      nameField,
      { key: 'category', label: '分类' },
      { key: 'unit', label: '单位' },
      { key: 'description', label: '描述', type: 'textarea' },
      activeSwitch,
    ],
    listTitle: (item) => String(item.display_name || item.name || item.code),
    listSub: (item) => [item.code, item.category, item.unit].filter(Boolean).join(' · '),
  }),

  skus: std('/admin/master/skus', {
    key: 'skus',
    title: '型号管理',
    permission: 'sku.manage',
    fields: [
      {
        key: 'product_id',
        label: '产品',
        type: 'select',
        required: true,
        refList: { path: '/admin/master/products', labelKeys: ['display_name', 'name', 'code'], valueKey: 'id' },
      },
      codeField,
      nameField,
      { key: 'color', label: '颜色' },
      { key: 'material', label: '材料' },
      { key: 'spec', label: '规格' },
      { key: 'remark', label: '备注', type: 'textarea' },
      activeSwitch,
    ],
    listTitle: (item) => String(item.display_label || item.name || item.code),
    listSub: (item) => [item.product_name, item.color, item.spec].filter(Boolean).join(' · '),
  }),

  suppliers: std('/admin/master/suppliers', {
    key: 'suppliers',
    title: '供应商',
    permission: 'supplier.manage',
    fields: [
      codeField,
      nameField,
      { key: 'contact_name', label: '联系人' },
      { key: 'phone', label: '电话', miniappExclude: true },
      { key: 'address', label: '地址', miniappExclude: true },
      { key: 'remark', label: '备注', type: 'textarea' },
      activeSwitch,
    ],
    ...titleCodeName(),
  }),

  materials: std('/admin/master/materials', {
    key: 'materials',
    title: '物料管理',
    permission: 'material.manage',
    fields: [
      codeField,
      nameField,
      { key: 'unit', label: '单位' },
      { key: 'spec', label: '规格' },
      {
        key: 'supplier_id',
        label: '供应商',
        type: 'select',
        refList: { path: '/admin/master/suppliers', labelKeys: ['name', 'code'], valueKey: 'id' },
      },
      { key: 'remark', label: '备注', type: 'textarea' },
      activeSwitch,
    ],
    ...titleCodeName(),
  }),

  processes: std('/admin/master/processes', {
    key: 'processes',
    title: '工序管理',
    permission: 'process.manage',
    fields: [
      codeField,
      nameField,
      { key: 'workshop', label: '车间' },
      { key: 'std_minutes', label: '标准工时(分)', type: 'number' },
      activeSwitch,
    ],
    listTitle: (item) => String(item.display_name || item.name || item.code),
    listSub: (item) => [item.code, item.workshop].filter(Boolean).join(' · '),
  }),

  processPrices: std('/admin/master/process-prices', {
    key: 'processPrices',
    title: '工序工价',
    permission: 'price.manage',
    fields: [
      {
        key: 'sku_id',
        label: '型号',
        type: 'select',
        required: true,
        refList: { path: '/admin/master/skus', labelKeys: ['display_label', 'name', 'code'], valueKey: 'id' },
      },
      {
        key: 'process_id',
        label: '工序',
        type: 'select',
        required: true,
        refList: { path: '/admin/master/processes', labelKeys: ['display_name', 'name', 'code'], valueKey: 'id' },
      },
      { key: 'unit_price', label: '单价(元)', type: 'number', required: true },
      activeSwitch,
    ],
    listTitle: (item) => {
      const sku = (item.sku as Record<string, unknown>)?.display_label || item.sku_id
      const proc = (item.process as Record<string, unknown>)?.name || item.process_id
      return `${sku} · ${proc}`
    },
    listSub: (item) => `¥${item.unit_price ?? '-'}`,
  }),

  processRoutes: std('/admin/master/process-routes', {
    key: 'processRoutes',
    title: '工艺路线',
    permission: 'product.manage',
    fields: [
      {
        key: 'product_id',
        label: '产品',
        type: 'select',
        required: true,
        refList: { path: '/admin/master/products', labelKeys: ['display_name', 'name', 'code'], valueKey: 'id' },
      },
      nameField,
      { key: 'is_default', label: '默认路线', type: 'switch' },
      activeSwitch,
    ],
    ...titleCodeName('路线'),
    beforeSubmit: (payload) => ({ ...payload, steps: [] }),
  }),

  boms: std('/admin/master/boms', {
    key: 'boms',
    title: 'BOM',
    permission: 'bom.manage',
    fields: [
      {
        key: 'scope',
        label: '范围',
        type: 'select',
        required: true,
        options: [
          { label: '型号BOM', value: 'sku' },
          { label: '产品默认', value: 'product' },
          { label: '全局', value: 'global' },
        ],
      },
      {
        key: 'sku_id',
        label: '型号',
        type: 'select',
        refList: { path: '/admin/master/skus', labelKeys: ['display_label', 'name', 'code'], valueKey: 'id' },
      },
      {
        key: 'product_id',
        label: '产品',
        type: 'select',
        refList: { path: '/admin/master/products', labelKeys: ['display_name', 'name', 'code'], valueKey: 'id' },
      },
      { key: 'name', label: 'BOM名称' },
      { key: 'version', label: '版本', type: 'number' },
      { key: 'remark', label: '备注', type: 'textarea' },
      { key: 'is_default', label: '默认', type: 'switch' },
    ],
    listTitle: (item) => String(item.name || item.sku_name || item.product_name || `BOM#${item.id}`),
    listSub: (item) => [item.scope, item.version != null ? `v${item.version}` : ''].filter(Boolean).join(' · '),
    beforeSubmit: (payload) => ({ ...payload, items: [] }),
  }),

  customers: std('/admin/production/customers', {
    key: 'customers',
    title: '客户管理',
    permission: 'customer.manage',
    fields: [
      codeField,
      nameField,
      { key: 'contact_name', label: '联系人' },
      { key: 'contact_phone', label: '电话', miniappExclude: true },
      { key: 'address', label: '地址', miniappExclude: true },
      { key: 'remark', label: '备注', type: 'textarea' },
      activeSwitch,
    ],
    ...titleCodeName(),
  }),

  users: std('/admin/system/users', {
    key: 'users',
    title: '用户管理',
    permission: 'user.manage',
    fields: [
      { key: 'username', label: '用户名', required: true, createOnly: true },
      { key: 'password', label: '密码', type: 'password', required: true, createOnly: true },
      { key: 'password', label: '新密码(可选)', type: 'password', editOnly: true },
      { key: 'full_name', label: '姓名' },
      {
        key: 'department_id',
        label: '部门',
        type: 'select',
        refList: { path: '/admin/system/departments', labelKeys: ['name', 'code'], valueKey: 'id' },
      },
      { key: 'is_superuser', label: '超级管理员', type: 'switch' },
      activeSwitch,
    ],
    listTitle: (item) => String(item.full_name || item.username),
    listSub: (item) => {
      const roles = (item.roles as { name?: string }[] | undefined)?.map((r) => r.name).join(', ')
      return [item.username, roles].filter(Boolean).join(' · ')
    },
    beforeSubmit: (payload, mode) => {
      const p = { ...payload }
      if (mode === 'edit' && !p.password) delete p.password
      return p
    },
  }),

  roles: std('/admin/system/roles', {
    key: 'roles',
    title: '角色管理',
    permission: 'role.manage',
    fields: [
      { key: 'code', label: '角色编码', required: true },
      { key: 'name', label: '角色名称', required: true },
    ],
    listTitle: (item) => String(item.name || item.code),
    listSub: (item) => String(item.code || ''),
    deleteLabel: '删除',
  }),

  permissions: std('/admin/system/permissions', {
    key: 'permissions',
    title: '权限点',
    permission: 'permission.manage',
    fields: [
      { key: 'code', label: '权限编码', required: true },
      { key: 'name', label: '权限名称', required: true },
    ],
    listTitle: (item) => String(item.name || item.code),
    listSub: (item) => String(item.code || ''),
    deleteLabel: '删除',
  }),

  skills: std('/admin/system/skills', {
    key: 'skills',
    title: '技能标签',
    permission: 'skill.manage',
    fields: [codeField, nameField, activeSwitch],
    ...titleCodeName(),
  }),

  printTemplates: std('/admin/system/print-templates', {
    key: 'printTemplates',
    title: '打印模板',
    permission: 'print_template.manage',
    fields: [
      { key: 'code', label: '模板编码', required: true },
      { key: 'name', label: '模板名称', required: true },
      { key: 'template_type', label: '类型', placeholder: 'html' },
      { key: 'content', label: '模板内容', type: 'textarea', required: true },
      activeSwitch,
    ],
    ...titleCodeName('模板'),
  }),

  equipment: {
    key: 'equipment',
    title: '设备管理',
    permission: 'equipment.manage',
    listPath: '/admin/equipment',
    createPath: '/admin/equipment',
    createOnly: true,
    fields: [
      codeField,
      nameField,
      { key: 'model', label: '型号' },
      { key: 'workshop', label: '车间' },
      { key: 'remark', label: '备注', type: 'textarea' },
    ],
    listTitle: (item) => String(item.name || item.code),
    listSub: (item) => [item.code, item.status, item.workshop].filter(Boolean).join(' · '),
    deleteLabel: '停用',
  },

  warehouses: {
    key: 'warehouses',
    title: '仓库管理',
    permission: 'warehouse.manage',
    listPath: '/admin/warehouse/warehouses',
    createPath: '/admin/warehouse/warehouses',
    updatePath: (id) => `/admin/warehouse/warehouses/${id}`,
    updateAsQuery: true,
    fields: [codeField, nameField, { key: 'address', label: '地址', miniappExclude: true }],
    ...titleCodeName(),
    deleteLabel: '停用',
  },

  crmTags: std('/admin/production/crm/tags', {
    key: 'crmTags',
    title: '客户标签',
    permission: 'customer.manage',
    fields: [
      { key: 'name', label: '标签名', required: true },
      { key: 'color', label: '颜色', placeholder: '#409eff' },
      activeSwitch,
    ],
    listTitle: (item) => String(item.name),
    listSub: (item) => String(item.color || ''),
  }),

  operationLogs: {
    key: 'operationLogs',
    title: '操作日志',
    permission: 'operation_log.view',
    listPath: '/admin/system/operation-logs',
    readonly: true,
    fields: [],
    listTitle: (item) => String(item.action || item.module || `#${item.id}`),
    listSub: (item) => `${item.username || ''} ${item.detail || item.path || ''}`.trim(),
  },

  attendanceRecords: std('/admin/system/attendance-records', {
    key: 'attendanceRecords',
    title: '考勤记录',
    permission: 'attendance.manage',
    fields: [
      { key: 'user_id', label: '用户ID', type: 'number', required: true },
      { key: 'work_date', label: '日期', type: 'date', required: true },
      { key: 'check_in_at', label: '上班', placeholder: 'HH:mm 或留空' },
      { key: 'check_out_at', label: '下班', placeholder: 'HH:mm 或留空' },
      { key: 'remark', label: '备注' },
    ],
    listTitle: (item) => String(item.user_name || item.user_id || item.id),
    listSub: (item) => [item.work_date, item.status].filter(Boolean).join(' · '),
    deleteLabel: '删除',
  }),
}

export function getCrudSchema(key: string): CrudSchema {
  const schema = ADMIN_CRUD_SCHEMAS[key]
  if (!schema) throw new Error(`未知 CRUD schema: ${key}`)
  return schema
}
