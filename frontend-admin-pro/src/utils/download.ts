// Copyright (C) 2026 CenkorMES Project
// SPDX-License-Identifier: AGPL-3.0
/** 把接口返回的 Blob 存成文件。createObjectURL 不 revoke 会一直占着内存。 */
export function saveBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}
