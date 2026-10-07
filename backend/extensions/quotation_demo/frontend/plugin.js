/* 报价单（演示扩展）前端插件
 * 由 admin 前端「扩展加载器」在登录后拉取并注入执行。
 * 协议：调用 window.__registerExtension({ key, menus, routes, locales })
 * - Vue 运行时由宿主注入到 window.Vue（与插件构建 external 配置对应）
 * - routes 的 component 必须是组件定义对象（打包进本文件），不能用字符串懒加载
 */
;(function () {
  var Vue = window.Vue
  if (!Vue || !window.__registerExtension) {
    console.warn('[quotation_demo] 宿主未提供注册桥，跳过注册')
    return
  }

  var DemoPage = {
    name: 'QuotationDemoPage',
    render: function () {
      return Vue.h(
        'div',
        { style: 'padding:24px;background:#fff;border-radius:12px' },
        [
          Vue.h('h2', { style: 'margin:0 0 12px' }, '报价单（演示扩展）'),
          Vue.h(
            'p',
            { style: 'color:#666' },
            '本页面由扩展 plugin.js 动态注册，数据来自 /api/extensions/quotation_demo/quotes。'
          ),
        ]
      )
    },
  }

  window.__registerExtension({
    key: 'quotation_demo',
    menus: [
      { title: '报价单（演示）', path: '/ext/quotation-demo', icon: 'Document', permission: 'ext.quotation.view' },
    ],
    routes: [
      { path: '/ext/quotation-demo', name: 'ext-quotation-demo', component: DemoPage },
    ],
    locales: {
      zh: { menu: { quotationDemo: '报价单（演示）' } },
      en: { menu: { quotationDemo: 'Quotation (Demo)' } },
    },
  })
})()
