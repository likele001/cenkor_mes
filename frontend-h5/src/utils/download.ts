// Copyright (C) 2026 CenkorMES Project
// SPDX-License-Identifier: AGPL-3.0
// 统一的文本文件下载：H5 里把报告存成 .md 发给同事，比复制一大段文字实用
export function downloadText(
  filename: string,
  content: string,
  mime = 'text/markdown;charset=utf-8',
): boolean {
  try {
    const url = URL.createObjectURL(new Blob([content], { type: mime }))
    const a = document.createElement('a')
    a.href = url
    a.download = filename
    a.click()
    URL.revokeObjectURL(url)
    return true
  } catch {
    return false
  }
}
