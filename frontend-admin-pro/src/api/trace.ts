import { http } from '@/utils/http'

/** 追溯树节点（递归结构） */
export interface TreeNode {
  id: number
  code: string
  product_code?: string | null
  task_seq: number | null
  qty: number
  remark: string | null
  created_at: string
  piece_no?: string | null
  process: { id: number; code: string; name: string } | null
  order: { id: number; code: string; status: string } | null
  sku: { id: number; code: string; name: string } | null
  report: { id: number; good_qty: number; bad_qty: number; status: string } | null
  report_unit: { id: number; unit_seq: number | null; result_type: string | null; status: string } | null
  user: { id: number; full_name: string | null; username: string | null } | null
  children?: TreeNode[]
}

/** 层级追溯树接口返回 */
export interface TraceTree {
  product_code: string
  order: { id: number; code: string; status: string } | null
  sku: { id: number; code: string; name: string } | null
  total_nodes: number
  tree: TreeNode[]
}

export const traceApi = {
  /** 按成品码获取层级追溯树 */
  getTree(productCode: string) {
    return http.request<TraceTree>({
      url: `/admin/trace/tree/${encodeURIComponent(productCode)}`,
      method: 'GET',
    })
  },
}
