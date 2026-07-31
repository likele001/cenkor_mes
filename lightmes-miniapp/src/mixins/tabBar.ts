type TabBarApi = {
  refreshList?: () => void
  setSelectedByPath?: (path: string) => void
}

export function syncTabBarSelected() {
  const pages = getCurrentPages()
  const page = pages[pages.length - 1] as { route?: string; getTabBar?: () => TabBarApi }
  const tabBar = page?.getTabBar?.()
  if (!tabBar) return
  tabBar.refreshList?.()
  if (tabBar.setSelectedByPath) {
    const route = '/' + (page.route || '')
    tabBar.setSelectedByPath(route)
  }
}

export function updateTabBarBadge(count: number) {
  const pages = getCurrentPages()
  const page = pages[pages.length - 1] as { getTabBar?: () => ({ setBadge?: (idx: number, count: number) => void }) }
  const tabBar = page?.getTabBar?.()
  if (tabBar?.setBadge) {
    tabBar.setBadge(4, count)
  }
}
