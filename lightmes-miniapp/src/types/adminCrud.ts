export type CrudFieldType = 'text' | 'number' | 'textarea' | 'switch' | 'select' | 'date' | 'password'

export type CrudFieldOption = { label: string; value: string | number | boolean }

export type CrudField = {
  key: string
  label: string
  type?: CrudFieldType
  required?: boolean
  placeholder?: string
  createOnly?: boolean
  editOnly?: boolean
  hiddenOnCreate?: boolean
  /** 微信审核敏感项：小程序不展示输入框，请在 PC 管理端维护 */
  miniappExclude?: boolean
  options?: CrudFieldOption[]
  /** 从其它列表接口加载选项 */
  refList?: {
    path: string
    labelKeys?: string[]
    valueKey?: string
  }
}

export type CrudSchema = {
  key: string
  title: string
  permission: string
  listPath: string
  listMethod?: 'GET'
  createPath?: string
  updatePath?: (id: number | string) => string
  deletePath?: (id: number | string) => string
  getPath?: (id: number | string) => string
  deleteLabel?: string
  readonly?: boolean
  keywordParam?: string
  listTitle: (item: Record<string, unknown>) => string
  listSub?: (item: Record<string, unknown>) => string
  fields: CrudField[]
  /** 提交前转换 */
  beforeSubmit?: (payload: Record<string, unknown>, mode: 'create' | 'edit') => Record<string, unknown>
  /** PUT 时使用 query 参数（如仓库） */
  updateAsQuery?: boolean
  /** 仅允许新增，不可编辑/停用 */
  createOnly?: boolean
  /** 打开编辑表单前 */
  mapRecordToForm?: (item: Record<string, unknown>) => Record<string, unknown>
}
