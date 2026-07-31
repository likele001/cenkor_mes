const EMPLOYEE_TABS = [
  { pagePath: '/pages/tabs/tab-0/index', text: '首页', icon: '⌂' },
  { pagePath: '/pages/tabs/tab-1/index', text: '任务', icon: '☰' },
  { pagePath: '/pages/tabs/tab-2/index', text: '报工', icon: '◎', center: true },
  { pagePath: '/pages/tabs/tab-3/index', text: '打卡', icon: '◷' },
  { pagePath: '/pages/tabs/tab-4/index', text: '我的', icon: '☺' },
]

const ADMIN_TABS = [
  { pagePath: '/pages/tabs/tab-0/index', text: '工作台', icon: '⌂' },
  { pagePath: '/pages/tabs/tab-1/index', text: '功能', icon: '☷' },
  { pagePath: '/pages/tabs/tab-2/index', text: '审核', icon: '✓' },
  { pagePath: '/pages/tabs/tab-3/index', text: '消息', icon: '🔔' },
  { pagePath: '/pages/tabs/tab-4/index', text: '我的', icon: '☺' },
]

const MODE_KEY = 'lightmes_app_mode'

Component({
  data: {
    selected: 0,
    list: EMPLOYEE_TABS,
    badges: [0, 0, 0, 0, 0],
  },
  lifetimes: {
    attached() {
      this.refreshList()
    },
  },
  pageLifetimes: {
    show() {
      this.refreshList()
    },
  },
  methods: {
    refreshList() {
      const mode = wx.getStorageSync(MODE_KEY) || 'employee'
      this.setData({
        list: mode === 'admin' ? ADMIN_TABS : EMPLOYEE_TABS,
      })
    },
    onSwitchTab(e) {
      const index = e.currentTarget.dataset.index
      const path = e.currentTarget.dataset.path
      this.setData({ selected: index })
      wx.switchTab({ url: path })
    },
    setSelectedByPath(path) {
      const route = path && path.charAt(0) === '/' ? path : '/' + (path || '')
      const list = this.data.list || []
      let idx = -1
      for (let i = 0; i < list.length; i++) {
        const seg = (list[i].pagePath || '').replace(/^\//, '')
        if (seg && route.indexOf(seg) >= 0) {
          idx = i
          break
        }
      }
      if (idx >= 0) {
        this.setData({ selected: idx })
      }
    },
    setBadge(index, count) {
      const key = `badges[${index}]`
      this.setData({ [key]: Math.max(0, count) })
    },
  },
})
