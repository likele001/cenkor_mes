export interface GuideSection {
  id: string
  title: string
  content?: string
  children?: GuideSection[]
}

const guideData: GuideSection[] = [
  {
    id: 'part1',
    title: '员工端使用指南',
    children: [
      {
        id: 'emp-ch1',
        title: '登录与首页',
        children: [
          {
            id: 'emp-1-1',
            title: '登录与认证',
            content: `<h3>登录与身份认证</h3>
<p><strong>适用用户</strong>：工厂员工 / 操作工人</p>
<p><strong>访问方式</strong>：手机浏览器打开 H5 链接，或扫描工厂发放的二维码</p>
<h4>首次登录</h4>
<ol>
<li>在手机浏览器输入应用 URL，或扫描二维码</li>
<li>输入用户名（通常是工号）和密码</li>
<li>首次登录需修改初始密码</li>
<li>成功后自动跳转到首页</li>
</ol>
<h4>注意事项</h4>
<ul>
<li>账户由 HR 分配，联系人力资源部获取</li>
<li>忘记密码：点击「忘记密码」→ 输入手机号 → 验证码 → 重置</li>
<li>15分钟无操作自动退出</li>
<li>工作完毕记得退出登录</li>
</ul>`
          },
          {
            id: 'emp-1-2',
            title: '首页仪表盘',
            content: `<h3>首页仪表盘</h3>
<h4>页面布局</h4>
<ul>
<li><strong>账户信息栏</strong>：显示姓名、部门、日期</li>
<li><strong>今日概览卡片</strong>：
<ul>
<li>待报工：还未报工的任务数</li>
<li>已报工：已提交报工数</li>
<li>待审核：班组长待初审的报工数</li>
<li>今日工资：基于已审核报工的实时估算</li>
</ul></li>
<li><strong>快速操作按钮</strong>：我的任务、扫码报工、打卡</li>
<li><strong>待办提醒</strong>：新任务、驳回通知等</li>
<li><strong>本周产量趋势图</strong></li>
</ul>`
          },
        ]
      },
      {
        id: 'emp-ch2',
        title: '任务与报工',
        children: [
          {
            id: 'emp-2-1',
            title: '我的任务',
            content: `<h3>我的任务</h3>
<p><strong>路径</strong>：首页「我的任务」或底部导航「任务」</p>
<h4>任务列表</h4>
<ul>
<li>显示派给自己的所有任务</li>
<li>每项任务卡片显示：任务编码、产品信息、工序名称、派工数量、进度、状态</li>
<li><strong>任务状态</strong>：待开始 / 生产中 / 已完成 / 已驳回</li>
<li>可按工序、状态筛选，按产品名/订单号搜索</li>
</ul>
<h4>任务操作</h4>
<ul>
<li>点击任务查看详情</li>
<li>点击「扫码报工」进入报工流程</li>
</ul>`
          },
          {
            id: 'emp-2-2',
            title: '扫码报工',
            content: `<h3>扫码报工</h3>
<p><strong>路径</strong>：首页「扫码报工」或底部导航「报工」</p>
<h4>完整报工流程</h4>
<ol>
<li><strong>扫码识别</strong>：扫描任务二维码，系统自动识别任务</li>
<li><strong>输入数量</strong>：输入合格数和不良数（合格+不良 ≤ 派工数）</li>
<li><strong>上传证据</strong>：
<ul>
<li>照片：1-5张，JPG/PNG，每张 ≤ 5MB</li>
<li>视频：最长30秒，MP4 格式，≤ 10MB</li>
</ul></li>
<li><strong>填写备注</strong>：如有异常或特殊情况</li>
<li><strong>确认提交</strong>：提交后立即显示预估工资</li>
</ol>
<h4>预估工资计算</h4>
<p><code>预估工资 = 合格数 × 工序工价</code></p>
<p>注意：这是预估值，最终工资需要审核通过后才确认。</p>
<h4>注意事项</h4>
<ul>
<li>数据要真实准确，虚报影响工资和信誉</li>
<li>照片要清晰展示产品细节</li>
<li>如有问题一定在备注中说明</li>
<li>提交后不可修改，被驳回可重新报工</li>
</ul>`
          },
          {
            id: 'emp-2-3',
            title: '报工审核流程',
            content: `<h3>报工审核流程</h3>
<h4>多级审核</h4>
<ol>
<li><strong>班组长初审</strong>：
<ul>
<li>查看报工照片/视频</li>
<li>核实合格数和不良数是否合理</li>
<li>通过 → 进入 QC 终审</li>
<li>驳回 → 填写原因，员工重新报工</li>
</ul></li>
<li><strong>QC 终审</strong>：
<ul>
<li>从质检角度审核产品质量</li>
<li>通过 → 报工生效，自动计入工资</li>
<li>驳回 → 填写质检原因，返回员工</li>
</ul></li>
</ol>
<h4>审核周期</h4>
<ul>
<li>班组长初审：通常在报工后 1-2 小时内完成</li>
<li>QC 终审：初审通过后 1 个工作日内完成</li>
<li>全部审核通过后，报工数据即可进入工资计算</li>
</ul>`
          },
        ]
      },
      {
        id: 'emp-ch3',
        title: '工资与考勤',
        children: [
          {
            id: 'emp-3-1',
            title: '我的工资',
            content: `<h3>我的工资</h3>
<p><strong>路径</strong>：底部导航「我的」→「工资」</p>
<h4>月工资汇总</h4>
<ul>
<li>选择月份查看</li>
<li><strong>计件工资</strong>：基于审核通过的报工合格数 × 工序工价</li>
<li><strong>补贴</strong>：全勤奖、岗位津贴等</li>
<li><strong>扣款</strong>：迟到扣款、罚款等</li>
<li><strong>实发金额</strong>：计件工资 + 补贴 - 扣款</li>
</ul>
<h4>工序报工明细</h4>
<p>显示每笔报工的工序名称、合格数、单价和金额，完全透明可查。</p>`
          },
          {
            id: 'emp-3-2',
            title: '电子工资条',
            content: `<h3>电子工资条</h3>
<p><strong>路径</strong>：我的 → 工资条</p>
<h4>功能特点</h4>
<ul>
<li>三种查看模式：简洁版、详细版、PDF 下载</li>
<li>显示完整的工资明细和各项金额</li>
<li><strong>电子签名</strong>：确认工资后可签名确认</li>
<li>有异议可选择「拒绝签名」并提交问题</li>
<li>支持 PDF 下载和打印</li>
</ul>
<h4>注意事项</h4>
<ul>
<li>签名后视为确认工资，不可再修改</li>
<li>有异议先和班组长沟通，再联系财务</li>
<li>在下月发薪前完成签名</li>
</ul>`
          },
          {
            id: 'emp-3-3',
            title: '考勤打卡',
            content: `<h3>考勤打卡</h3>
<p><strong>路径</strong>：首页「打卡」或「我的」→「考勤打卡」</p>
<h4>操作步骤</h4>
<ol>
<li><strong>签到</strong>：上班时点击「签到」按钮，系统记录签到时间</li>
<li><strong>签退</strong>：下班时点击「签退」按钮，显示工作时长</li>
</ol>
<h4>打卡记录</h4>
<p>显示最近打卡记录：日期、签到时间、签退时间、工作时长、状态（准时/迟到）。</p>
<h4>注意事项</h4>
<ul>
<li>准时打卡，避免迟到扣款</li>
<li>忘记打卡可申请补卡（需班组长审批）</li>
<li>迟到15分钟起扣款，累计迟到影响全勤奖</li>
</ul>`
          },
        ]
      },
      {
        id: 'emp-ch4',
        title: '常见问题',
        children: [
          {
            id: 'emp-4-1',
            title: '员工常见问题',
            content: `<h3>员工常见问题</h3>
<h4>Q1：怎样快速报工？</h4>
<p>推荐使用<strong>扫码报工</strong>：打开手机端 → 首页「扫码报工」→ 扫描二维码 → 输入合格数/不良数 → 提交，整个流程不超过30秒。</p>
<h4>Q2：报工被驳回了，怎么办？</h4>
<ol>
<li>查看驳回原因通知</li>
<li>进入「我的任务」找到被驳回的任务</li>
<li>根据反馈重新报工（可修正数据和照片）</li>
</ol>
<h4>Q3：报工多久能到账工资？</h4>
<ul>
<li>报工提交 → 预估工资：立即（秒级）</li>
<li>预估 → 最终工资（审核通过）：1-3天</li>
<li>月工资最终确认：月底或次月初</li>
</ul>
<h4>Q4：如何避免报工被驳回？</h4>
<ul>
<li>数字准确：不虚报</li>
<li>拍好照片：至少3张，清晰展示产品</li>
<li>写好备注：有问题一定说明</li>
<li>及时报工：当天完成当天报</li>
<li>不确定时先问班组长</li>
</ul>
<h4>Q5：员工端和客户端有什么区别？</h4>
<p><strong>员工端</strong>可查看任务、扫码报工、查看工资、打卡；<strong>客户端</strong>可下单、查看订单进度、对账单。用员工工号登录进入员工端，用客户账号登录进入客户端。</p>`
          },
        ]
      },
    ]
  },
  {
    id: 'part2',
    title: '客户端使用指南',
    children: [
      {
        id: 'cust-ch1',
        title: '登录与下单',
        children: [
          {
            id: 'cust-1-1',
            title: '登录与认证',
            content: `<h3>登录与认证</h3>
<p><strong>适用用户</strong>：客户 / 会员用户</p>
<p><strong>访问方式</strong>：手机浏览器打开 H5 链接，或扫描企业提供的二维码</p>
<h4>登录步骤</h4>
<ol>
<li>打开应用，进入登录页</li>
<li>输入用户名（手机号或账号）和密码</li>
<li>点击「登录」，系统验证身份</li>
<li>首次登录可能需要完善用户资料</li>
</ol>
<h4>注意事项</h4>
<ul>
<li>账户由企业分配，联系销售或客服获取</li>
<li>忘记密码：点击「忘记密码」→ 输入手机号 → 验证码 → 重置</li>
<li>15分钟未操作自动退出</li>
</ul>`
          },
          {
            id: 'cust-1-2',
            title: '客户下单',
            content: `<h3>客户下单</h3>
<p><strong>路径</strong>：底部导航「下单」或首页「我要下单」</p>
<h4>下单流程</h4>
<ol>
<li><strong>浏览产品</strong>：进入下单页面，显示产品列表，可按分类过滤或搜索</li>
<li><strong>选择型号</strong>：点击产品，选择需要的型号（颜色、材料、规格）</li>
<li><strong>输入信息</strong>：填写订单数量、交期（建议至少7天后）、特殊要求备注</li>
<li><strong>提交订单</strong>：点击「提交订单」→ 确认信息 → 订单提交成功</li>
</ol>
<h4>注意事项</h4>
<ul>
<li>确认型号和数量无误后再提交</li>
<li>建议提前7天下单，紧急订单请电话咨询</li>
<li>草稿状态的订单可修改，已确认后不可修改</li>
</ul>`
          },
        ]
      },
      {
        id: 'cust-ch2',
        title: '订单与进度',
        children: [
          {
            id: 'cust-2-1',
            title: '订单管理',
            content: `<h3>订单管理</h3>
<p><strong>路径</strong>：底部导航「订单」</p>
<h4>订单列表</h4>
<ul>
<li>显示所有历史订单（卡片形式）</li>
<li>按状态、时间筛选，搜索订单号</li>
<li>每张卡片显示：订单号、产品、数量、金额、状态、交期</li>
</ul>
<h4>订单详情</h4>
<ul>
<li>基本信息：订单号、创建时间、状态</li>
<li>产品信息：名称、型号、数量、单价</li>
<li>进度信息：当前工序、完成比例、预计完成时间</li>
<li>操作：查看进度、联系客服、下载文档</li>
</ul>
<h4>订单状态</h4>
<p>草稿 → 已确认 → 生产中 → 已完成 → 已发货 → 已取消</p>`
          },
          {
            id: 'cust-2-2',
            title: '订单进度追踪',
            content: `<h3>订单进度追踪</h3>
<p><strong>路径</strong>：底部导航「追踪」或订单详情「查看进度」</p>
<h4>进度查看</h4>
<ul>
<li><strong>时间线视图</strong>：显示各工序的完成状态（已完成/进行中/待开始）</li>
<li><strong>工序详情</strong>：派工人数、完成数量、预计完成时间</li>
<li><strong>自动刷新</strong>：每2分钟更新一次，也可手动刷新</li>
</ul>
<h4>注意事项</h4>
<ul>
<li>如显示「延迟」，说明可能无法按时交期，建议联系客服</li>
<li>生产完成时会自动推送通知</li>
</ul>`
          },
        ]
      },
      {
        id: 'cust-ch3',
        title: '对账与消息',
        children: [
          {
            id: 'cust-3-1',
            title: '对账单查看',
            content: `<h3>对账单查看</h3>
<p><strong>路径</strong>：「我的」→「对账单」</p>
<h4>操作步骤</h4>
<ol>
<li>按月选择对账单</li>
<li>查看对账明细：各订单号、产品、金额、状态</li>
<li>核对总金额、已付金额、待付金额</li>
<li>支持操作：下载 PDF、申请发票、确认对账、提出异议</li>
</ol>
<h4>注意事项</h4>
<ul>
<li>定期查看对账单，及时确认</li>
<li>如有不符，点击「提出异议」，财务3-5个工作日回复</li>
<li>已确认的对账单不可再修改</li>
</ul>`
          },
          {
            id: 'cust-3-2',
            title: '消息通知',
            content: `<h3>消息通知</h3>
<p><strong>路径</strong>：「我的」→「消息中心」</p>
<h4>消息类型</h4>
<ul>
<li>订单确认通知、生产开始通知</li>
<li>工序完成通知、生产完成通知</li>
<li>已发货通知、对账单通知</li>
<li>系统通知</li>
</ul>
<h4>消息管理</h4>
<ul>
<li>消息列表按时间倒序显示</li>
<li>已读/未读标记</li>
<li>可删除单条或清空所有消息</li>
<li>可配置推送开关和不打扰时段</li>
</ul>`
          },
        ]
      },
      {
        id: 'cust-ch4',
        title: '常见问题',
        children: [
          {
            id: 'cust-4-1',
            title: '客户常见问题',
            content: `<h3>客户常见问题</h3>
<h4>Q1：提交订单后可以修改吗？</h4>
<p><strong>草稿状态</strong>：可以修改，进入订单详情点击「编辑」修改数量或交期。<br>
<strong>已确认状态</strong>：不能修改，需作废原订单重新下单，或联系客服。</p>
<h4>Q2：如何知道订单是否按时完成？</h4>
<p>三种方式：1. 消息推送通知 2. 「订单追踪」实时查看 3. 订单列表显示预计完成时间</p>
<h4>Q3：进度显示「延迟」是什么意思？</h4>
<p>表示可能无法按时完成，建议立即联系客服了解情况和解决方案。</p>
<h4>Q4：对账单金额与我的账目不符怎么办？</h4>
<ol>
<li>仔细核对每个订单号和金额</li>
<li>检查是否有已取消订单被包含</li>
<li>如仍不符，点击「提出异议」说明情况</li>
<li>财务会在3-5个工作日回复</li>
</ol>
<h4>Q5：如何联系工厂客服？</h4>
<ul>
<li>订单详情页点击「联系客服」</li>
<li>消息中心点击「询问工厂」</li>
<li>个人中心查看客服电话和微信</li>
</ul>`
          },
        ]
      },
    ]
  },
]

export function getGuideData(): GuideSection[] {
  return guideData
}

export function flattenSections(sections: GuideSection[]): GuideSection[] {
  const result: GuideSection[] = []
  function walk(list: GuideSection[]) {
    for (const s of list) {
      if (s.content) result.push(s)
      if (s.children) walk(s.children)
    }
  }
  walk(sections)
  return result
}

export function findSectionById(id: string): GuideSection | undefined {
  function walk(list: GuideSection[]): GuideSection | undefined {
    for (const s of list) {
      if (s.id === id) return s
      if (s.children) {
        const found = walk(s.children)
        if (found) return found
      }
    }
    return undefined
  }
  return walk(guideData)
}

export function getBreadcrumb(id: string): GuideSection[] {
  const path: GuideSection[] = []
  function walk(list: GuideSection[]): boolean {
    for (const s of list) {
      path.push(s)
      if (s.id === id) return true
      if (s.children && walk(s.children)) return true
      path.pop()
    }
    return false
  }
  walk(guideData)
  return path
}

export default guideData
