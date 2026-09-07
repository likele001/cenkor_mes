// Copyright (C) 2026 CenkorMES Project
// SPDX-License-Identifier: AGPL-3.0
export type ApiResp<T> = {
  code: number
  msg: string
  data: T
}

export type ListResp<T> = {
  items: T[]
}

