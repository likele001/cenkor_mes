export type ApiResp<T> = {
  code: number
  msg: string
  data: T
}

export type ListResp<T> = {
  items: T[]
}

