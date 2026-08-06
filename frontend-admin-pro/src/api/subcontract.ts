import { http } from '@/utils/http'
import type { ListResp } from '@/types/api'

export type SubcontractOrderBrief = {
  id: number
  code: string
  status: string
  supplier_id: number
  supplier_name: string | null
  created_at: string
}

export type SubcontractOrderItemOut = {
  id: number
  order_id: number
  sku_id: number
  process_id: number | null
  qty: number
  unit_price: string | null
  sent_qty: number
  received_qty: number
  remark: string | null
  sku_code: string | null
  sku_name: string | null
  process_name: string | null
}

export type SendLogOut = {
  id: number
  order_id: number
  item_id: number
  qty: number
  remark: string | null
  created_at: string
  sku_code: string | null
  sku_name: string | null
}

export type ReceiveLogOut = {
  id: number
  order_id: number
  item_id: number
  qty: number
  remark: string | null
  created_at: string
  sku_code: string | null
  sku_name: string | null
}

export type SubcontractOrderOut = SubcontractOrderBrief & {
  remark: string | null
  created_by: number | null
  updated_at: string
  items: SubcontractOrderItemOut[]
  send_logs: SendLogOut[]
  receive_logs: ReceiveLogOut[]
}

export type SubcontractOrderCreateItemIn = {
  sku_id: number
  process_id?: number | null
  qty: number
  unit_price?: string | null
  remark?: string | null
}

export type SubcontractOrderCreateIn = {
  supplier_id: number
  code: string
  remark?: string | null
  items: SubcontractOrderCreateItemIn[]
}

export type SendLogIn = {
  item_id: number
  qty: number
  remark?: string | null
}

export type ReceiveLogIn = {
  item_id: number
  qty: number
  remark?: string | null
}

export const subcontractApi = {
  listOrders(params: any) {
    return http.request<ListResp<SubcontractOrderBrief>>({
      url: '/admin/subcontract',
      method: 'GET',
      params,
    })
  },
  createOrder(data: SubcontractOrderCreateIn) {
    return http.request<SubcontractOrderOut>({
      url: '/admin/subcontract',
      method: 'POST',
      data,
    })
  },
  getOrder(id: number) {
    return http.request<SubcontractOrderOut>({
      url: `/admin/subcontract/${id}`,
      method: 'GET',
    })
  },
  updateStatus(id: number, status: string) {
    return http.request<SubcontractOrderOut>({
      url: `/admin/subcontract/${id}/status`,
      method: 'PATCH',
      params: { status },
    })
  },
  sendLog(id: number, data: SendLogIn) {
    return http.request<SubcontractOrderOut>({
      url: `/admin/subcontract/${id}/send`,
      method: 'POST',
      data,
    })
  },
  receiveLog(id: number, data: ReceiveLogIn) {
    return http.request<SubcontractOrderOut>({
      url: `/admin/subcontract/${id}/receive`,
      method: 'POST',
      data,
    })
  },
}
