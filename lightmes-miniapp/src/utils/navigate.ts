// Copyright (C) 2026 CenkorMES Project
// SPDX-License-Identifier: AGPL-3.0
export function afterLoginNavigate() {
  uni.reLaunch({ url: '/pages/tabs/emp-home/index' })
}
