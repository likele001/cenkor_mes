/* 事件钩子（演示扩展）前端插件
 * 由 admin 前端「扩展加载器」在登录后拉取并注入执行。
 * 协议：调用 window.__registerExtension({ key, menus, routes, locales })
 * - Vue 运行时由宿主注入到 window.Vue（与插件构建 external 配置对应）
 * - routes 的 component 必须是组件定义对象（打包进本文件），不能用字符串懒加载
 */
;(function () {
  var Vue = window.Vue
  if (!Vue || !window.__registerExtension) {
    console.warn('[hook_demo] 宿主未提供注册桥，跳过注册')
    return
  }

  var DemoPage = {
    name: 'HookDemoPage',
    render: function () {
      return Vue.h(
        'div',
        { style: 'padding:24px;background:#fff;border-radius:12px' },
        [
          Vue.h('h2', { style: 'margin:0 0 12px' }, '报工统计（演示扩展）'),
          Vue.h(
            'p',
            { style: 'color:#666' },
            '本扩展订阅 report.submitted 事件，每次报工提交后自动记录一行。数据来自 /api/extensions/hook_demo/report-log。'
          ),
        ]
      )
    },
  }

  window.__registerExtension({
    key: 'hook_demo',
    menus: [
      { title: '报工统计（演示）', path: '/ext/hook-demo', icon: 'Connection', permission: 'ext.hook_demo.view' },
    ],
    routes: [
      { path: '/ext/hook-demo', name: 'ext-hook-demo', component: DemoPage },
    ],
    locales: {
      zh: { menu: { hookDemo: '报工统计（演示）' } },
      en: { menu: { hookDemo: 'Report Log (Demo)' } },
    },
  })
})()
