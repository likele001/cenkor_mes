<script setup lang="ts">
import { ref, onMounted, onUnmounted, computed } from 'vue'
import { useRouter } from 'vue-router'
import { getStoredTenantCode } from '@/utils/tenant'

const router = useRouter()

const loginPath = computed(() => {
  const code = getStoredTenantCode()
  return code ? `/t/${code}/login` : '/login'
})

function go(path: string) {
  router.push(path)
}

const activeId = ref('ch1')

const groups = [
  {
    title: '系统配置',
    items: [
      { id: 'ch1', label: '1. 用户与权限' },
      { id: 'ch2', label: '2. 部门与字典' },
      { id: 'ch3', label: '3. 通知与集成' },
    ],
  },
  {
    title: '主数据',
    items: [
      { id: 'ch4', label: '4. 产品与型号' },
      { id: 'ch5', label: '5. 工序与工艺路线' },
      { id: 'ch6', label: '6. 工价设置' },
      { id: 'ch7', label: '7. 物料与BOM' },
    ],
  },
  {
    title: '生产管理',
    items: [
      { id: 'ch8', label: '8. 订单与工单' },
      { id: 'ch9', label: '9. 排产与派工' },
      { id: 'ch10', label: '10. 报工与审核' },
      { id: 'ch11', label: '11. 进度看板' },
    ],
  },
  {
    title: '工资与财务',
    items: [
      { id: 'ch12', label: '12. 工资结算' },
      { id: 'ch13', label: '13. 客户对账' },
      { id: 'ch14', label: '14. 成本分析' },
    ],
  },
  {
    title: '员工H5端',
    items: [
      { id: 'ch15', label: '15. 员工登录与首页' },
      { id: 'ch16', label: '16. 扫码报工' },
      { id: 'ch17', label: '17. 工资与考勤' },
    ],
  },
  {
    title: '客户H5端',
    items: [
      { id: 'ch18', label: '18. 客户下单' },
      { id: 'ch19', label: '19. 订单追踪' },
      { id: 'ch20', label: '20. 常见问题' },
    ],
  },
  {
    title: '高级功能',
    items: [
      { id: 'ch21', label: '21. 模具管理' },
      { id: 'ch22', label: '22. 质检模板与缺陷代码' },
      { id: 'ch23', label: '23. 审批流程配置' },
      { id: 'ch24', label: '24. 排班管理' },
      { id: 'ch25', label: '25. 时薪管理' },
      { id: 'ch26', label: '26. 外协管理' },
      { id: 'ch27', label: '27. 出货管理' },
      { id: 'ch28', label: '28. AI 智能中心' },
      { id: 'ch29', label: '29. SPC 质量图表' },
    ],
  },
]

const allItems = computed(() => groups.flatMap(g => g.items))

function scrollToSection(id: string, block: ScrollLogicalPosition = 'start') {
  document.getElementById(id)?.scrollIntoView({ behavior: 'smooth', block })
}

function onMobileTocChange(event: Event) {
  const value = (event.target as HTMLSelectElement).value
  if (value) scrollToSection(value)
}

function updateActive() {
  const h2s = document.querySelectorAll('.doc-content h2[id]')
  let current = ''
  h2s.forEach(el => {
    const rect = el.getBoundingClientRect()
    if (rect.top <= 100) current = el.id
  })
  if (current) activeId.value = current
}

onMounted(() => window.addEventListener('scroll', updateActive))
onUnmounted(() => window.removeEventListener('scroll', updateActive))
</script>

<template>
  <div class="doc-root">
    <!-- NAV -->
    <nav class="doc-nav">
      <a class="doc-nav-logo" @click="go('/')">
        <div class="doc-nav-logo-icon">LM</div>
        <span>辰科MES</span>
      </a>
      <div class="doc-nav-links">
        <a @click="go('/')">首页</a>
        <a @click="go('/site/features')">功能</a>
        <a class="active">使用指南</a>
        <a :href="loginPath">登录系统</a>
      </div>
    </nav>

    <div class="doc-layout">
      <!-- SIDEBAR -->
      <aside class="doc-sidebar">
        <div v-for="g in groups" :key="g.title" class="group">
          <div class="group-title">{{ g.title }}</div>
          <a
            v-for="item in g.items"
            :key="item.id"
            :href="'#' + item.id"
            :class="{ active: activeId === item.id }"
            @click.prevent="scrollToSection(item.id)"
          >{{ item.label }}</a>
        </div>
      </aside>

      <!-- MOBILE TOC -->
      <div class="mobile-toc">
        <select :value="activeId" @change="onMobileTocChange">
          <option value="">跳转到章节...</option>
          <option v-for="item in allItems" :key="item.id" :value="item.id">{{ item.label }}</option>
        </select>
      </div>

      <!-- CONTENT -->
      <main class="doc-content">
        <h1>辰科MES 使用指南</h1>
        <p class="doc-subtitle">从系统配置到日常生产，分章节详细介绍 辰科MES 的每一项功能。涵盖管理员PC端、员工H5端、客户端完整操作流程。</p>

        <!-- CH1: 用户与权限 -->
        <h2 id="ch1">1. 用户与权限</h2>
        <p>系统管理员负责创建用户账号、分配角色和管理权限。</p>

        <h3>1.1 用户管理</h3>
        <p><strong>操作路径</strong>：系统 → 用户管理</p>
        <ol class="step-list">
          <li>点击 <strong>「+ 新建用户」</strong> 按钮</li>
          <li>填写用户名（全局唯一）、姓名、密码、部门、手机号</li>
          <li>选择角色（可多选，系统合并权限）</li>
          <li>点击 <strong>「保存」</strong> 完成创建</li>
        </ol>
        <div class="callout callout-warning">
          <div class="callout-title">注意</div>
          员工离职建议<strong>禁用</strong>而非删除，保留操作日志。首次登录强制修改密码。
        </div>

        <h3>1.2 角色管理</h3>
        <p><strong>操作路径</strong>：系统 → 角色管理</p>
        <p>系统内置 7 个角色，建议不要修改：</p>
        <table class="doc-table">
          <thead><tr><th>角色</th><th>说明</th><th>核心权限</th></tr></thead>
          <tbody>
            <tr><td>超级管理员</td><td>全部权限</td><td>所有</td></tr>
            <tr><td>厂长</td><td>生产/财务/报表</td><td>dashboard, report, salary</td></tr>
            <tr><td>生产计划员</td><td>订单/排产/派工</td><td>order, plan, task</td></tr>
            <tr><td>班组长</td><td>派工审核/报工审核</td><td>dispatch, report.audit</td></tr>
            <tr><td>操作员工</td><td>报工/查看任务</td><td>task, report</td></tr>
            <tr><td>客户</td><td>下单/查看进度</td><td>order.view</td></tr>
            <tr><td>财务</td><td>工资/对账/报表</td><td>salary, finance</td></tr>
          </tbody>
        </table>
        <div class="callout callout-info">
          <div class="callout-title">最小权限原则</div>
          只分配必要的权限。权限更新后需重新登录才能生效。
        </div>

        <!-- CH2: 部门与字典 -->
        <h2 id="ch2">2. 部门与字典</h2>

        <h3>2.1 部门管理</h3>
        <p><strong>操作路径</strong>：系统 → 部门管理</p>
        <ol class="step-list">
          <li>点击 <strong>「+ 新建部门」</strong></li>
          <li>填写部门名称（如"冲压车间""质检部"）、负责人、描述</li>
          <li>可设置上级部门建立层级关系</li>
        </ol>
        <p>启用了数据权限控制时，用户只能查看本部门数据。</p>

        <h3>2.2 字典管理</h3>
        <p><strong>操作路径</strong>：系统 → 字典管理</p>
        <p>系统预置了单位、颜色、工序分类、订单状态等字典。可新增字典值，但字典值代码保存后不可修改。</p>
        <div class="callout callout-warning">
          <div class="callout-title">重要</div>
          不要删除系统预置的关键字典（如订单状态、工序类型），否则会导致系统异常。
        </div>

        <!-- CH3: 通知与集成 -->
        <h2 id="ch3">3. 通知与集成</h2>

        <h3>3.1 飞书/企业微信通知</h3>
        <p><strong>操作路径</strong>：系统 → 飞书通知 / 企业微信通知</p>
        <ol class="step-list">
          <li>配置机器人 Webhook 地址</li>
          <li>创建通知群组，设置推送规则</li>
          <li>绑定用户账号（接收审核通知、工资条等）</li>
          <li>发送测试消息验证配置</li>
        </ol>

        <h3>3.2 打印模板</h3>
        <p><strong>操作路径</strong>：系统 → 打印模板</p>
        <p>支持自定义订单、工单、工资条等打印模板，使用变量渲染（如 <code>order.code</code>、<code>user.name</code>）。</p>

        <!-- CH4: 产品与型号 -->
        <h2 id="ch4">4. 产品与型号</h2>
        <p>产品和型号是两个独立模块，型号关联产品。</p>

        <h3>4.1 产品管理</h3>
        <p><strong>操作路径</strong>：主数据 → 产品</p>
        <ol class="step-list">
          <li>点击 <strong>「+ 新建产品」</strong></li>
          <li>填写产品编码（唯一）、名称、分类、单位、描述、主图</li>
          <li>支持 Excel 批量导入</li>
        </ol>

        <h3>4.2 产品型号（SKU）</h3>
        <p><strong>操作路径</strong>：主数据 → 产品型号</p>
        <ol class="step-list">
          <li>选择关联的产品</li>
          <li>填写型号编码（唯一）、颜色、材料、规格、备注</li>
          <li>上传多角度图片（正面/侧面/细节）</li>
          <li>支持 Excel 批量导入</li>
        </ol>
        <div class="callout callout-success">
          <div class="callout-title">提示</div>
          型号可启用/停用。停用的型号不可用于新订单，但不影响已有订单。
        </div>

        <!-- CH5: 工序与工艺路线 -->
        <h2 id="ch5">5. 工序与工艺路线</h2>

        <h3>5.1 工序管理</h3>
        <p><strong>操作路径</strong>：主数据 → 工序</p>
        <p>创建工厂的各个工序（如：下料、冲压、焊接、组装、质检），设置所属车间和标准工时。</p>
        <table class="doc-table">
          <thead><tr><th>编码</th><th>名称</th><th>车间</th><th>标准工时</th></tr></thead>
          <tbody>
            <tr><td>OP-010</td><td>下料</td><td>下料车间</td><td>0.5h/件</td></tr>
            <tr><td>OP-020</td><td>冲压</td><td>冲压车间</td><td>0.3h/件</td></tr>
            <tr><td>OP-030</td><td>焊接</td><td>焊接车间</td><td>0.8h/件</td></tr>
          </tbody>
        </table>

        <h3>5.2 工艺路线</h3>
        <p><strong>操作路径</strong>：主数据 → 工艺路线</p>
        <ol class="step-list">
          <li>选择产品，输入路线名称</li>
          <li>逐条添加工序步骤，拖拽调整顺序</li>
          <li>设置默认路线（一个产品只能有一个默认）</li>
        </ol>
        <p>工艺路线变更不影响已确认的订单，只有新订单才用新路线。</p>

        <!-- CH6: 工价设置 -->
        <h2 id="ch6">6. 工价设置</h2>
        <p>工价是计件工资的核心，按「产品型号 × 工序」设定单价（元/件）。</p>

        <h3>6.1 设置方法</h3>
        <p><strong>操作路径</strong>：主数据 → 工序工价</p>
        <ol class="step-list">
          <li>选择产品型号</li>
          <li>为每个工序输入单价（精度到 2 位小数）</li>
          <li>支持批量设置：一键为所有工序设置统一单价</li>
          <li>点击 <strong>「保存」</strong></li>
        </ol>
        <div class="callout callout-info">
          <div class="callout-title">历史追溯</div>
          工价变更后，旧订单按旧价、新订单按新价。系统自动记录变更历史。
        </div>

        <!-- CH7: 物料与BOM -->
        <h2 id="ch7">7. 物料与BOM</h2>

        <h3>7.1 物料管理</h3>
        <p><strong>操作路径</strong>：主数据 → 物料</p>
        <p>管理原材料信息：编码、名称、规格、单位、默认供应商、最低库存预警。</p>

        <h3>7.2 BOM（物料清单）</h3>
        <p><strong>操作路径</strong>：主数据 → BOM</p>
        <ol class="step-list">
          <li>选择产品，添加物料行</li>
          <li>设置每种物料的用量和损耗率</li>
          <li>BOM 支持版本管理，变更不影响已确认订单</li>
        </ol>

        <!-- CH8: 订单与工单 -->
        <h2 id="ch8">8. 订单与工单</h2>

        <h3>8.1 创建订单</h3>
        <p><strong>操作路径</strong>：生产 → 订单管理</p>
        <ol class="step-list">
          <li>点击 <strong>「+ 新建订单」</strong></li>
          <li>选择客户、产品型号、数量、交期</li>
          <li>保存后订单状态为 <strong>「草稿」</strong></li>
          <li>确认后自动分解为工单，状态变为 <strong>「已确认」</strong></li>
        </ol>
        <p>支持 Excel 批量导入订单。已确认的订单不可修改，需取消后重建。</p>

        <h3>8.2 订单状态流转</h3>
        <p>草稿 → 已确认 → 生产中 → 已完成 → 已发货 / 已取消</p>

        <!-- CH9: 排产与派工 -->
        <h2 id="ch9">9. 排产与派工</h2>

        <h3>9.1 生产计划</h3>
        <p><strong>操作路径</strong>：生产 → 生产计划</p>
        <ol class="step-list">
          <li>查看待排产工单列表</li>
          <li>在甘特图上<strong>拖拽</strong>调整起止日期</li>
          <li>系统自动检查物料齐套，缺料时提示</li>
          <li>点击 <strong>「发布计划」</strong></li>
        </ol>

        <h3>9.2 任务派工</h3>
        <p><strong>操作路径</strong>：生产 → 任务派工</p>
        <ol class="step-list">
          <li>选择工单，系统按技能标签推荐员工</li>
          <li>选择员工和派工数量</li>
          <li>生成任务二维码，可打印粘贴在工件上</li>
          <li>系统自动推送通知到员工手机端</li>
        </ol>

        <!-- CH10: 报工与审核 -->
        <h2 id="ch10">10. 报工与审核</h2>

        <h3>10.1 员工报工</h3>
        <p>员工在手机端扫码或手动选择任务，输入合格数/不良数，上传完工照片/视频，提交后立即显示预估工资。</p>

        <h3>10.2 多级审核</h3>
        <p><strong>操作路径</strong>：生产 → 报工审核</p>
        <ol class="step-list">
          <li><strong>班组长初审</strong>：查看照片/视频，核实数量，通过或驳回</li>
          <li><strong>QC 终审</strong>：质检角度审核，通过后报工生效</li>
          <li>驳回需填写原因，员工收到通知后重新报工</li>
          <li>支持批量审核，提高效率</li>
        </ol>
        <div class="callout callout-info">
          <div class="callout-title">工资计算</div>
          只有<strong>审核通过</strong>的报工才会计入工资。未审核或被驳回的报工不计入。
        </div>

        <!-- CH11: 进度看板 -->
        <h2 id="ch11">11. 进度看板</h2>

        <h3>11.1 首页仪表盘</h3>
        <p>管理员首页显示今日产值、订单达成率、不良率、待办事项等关键指标。</p>

        <h3>11.2 进度看板</h3>
        <p><strong>操作路径</strong>：仪表盘 → 进度看板</p>
        <p>显示所有订单的实时进度、各工序完成比例、交期倒计时。快逾期的订单高亮显示。</p>

        <h3>11.3 车间大屏</h3>
        <p><strong>操作路径</strong>：仪表盘 → 车间大屏</p>
        <p>全屏暗色主题，实时滚动产量、良率、异常报警、交期倒计时、员工排名。建议投放在车间显眼位置。</p>

        <!-- CH12: 工资结算 -->
        <h2 id="ch12">12. 工资结算</h2>

        <h3>12.1 自动计算</h3>
        <p><strong>操作路径</strong>：生产 → 工资管理</p>
        <p><strong>公式</strong>：<code>月总工资 = Σ(审核通过报工合格数 × 工序工价) + 补贴 - 扣款</code></p>
        <ol class="step-list">
          <li>选择月份，系统自动汇总所有审核通过的报工</li>
          <li>查看员工工资明细（工序数量、合格数、单价、金额）</li>
          <li>可手动添加补贴（全勤奖）或扣款（迟到）</li>
          <li>确认后生成电子工资条，支持导出 Excel</li>
        </ol>

        <h3>12.2 电子工资条</h3>
        <p>员工在手机端查看工资条明细，支持电子签名确认。有异议可拒绝签名并提交问题。</p>

        <!-- CH13: 客户对账 -->
        <h2 id="ch13">13. 客户对账</h2>
        <p><strong>操作路径</strong>：财务 → 客户对账单</p>
        <ol class="step-list">
          <li>选择客户和对账周期</li>
          <li>系统自动列出该周期内所有订单及金额</li>
          <li>核实无误后，对账单发送给客户</li>
          <li>客户确认后结束对账，支持导出 PDF/Excel</li>
        </ol>

        <!-- CH14: 成本分析 -->
        <h2 id="ch14">14. 成本分析</h2>
        <p><strong>操作路径</strong>：财务 → 成本毛利</p>
        <p>按订单维度分析：收入、工资成本、物料成本、毛利/毛利率。支持趋势图和产品对比。</p>
        <div class="callout callout-success">
          <div class="callout-title">经营决策</div>
          定期分析毛利，识别低毛利产品。用毛利数据指导定价策略和产能分配。
        </div>

        <!-- CH15: 员工登录与首页 -->
        <h2 id="ch15">15. 员工登录与首页</h2>

        <h3>15.1 登录</h3>
        <ol class="step-list">
          <li>在手机浏览器输入 H5 地址，或扫描工厂发放的二维码</li>
          <li>输入用户名（通常是工号）和密码</li>
          <li>首次登录需修改初始密码</li>
        </ol>

        <h3>15.2 首页仪表盘</h3>
        <p>登录后显示今日概览（待报工、已报工、待审核、今日工资）、快速操作按钮、待办提醒、本周产量趋势图。</p>

        <!-- CH16: 扫码报工 -->
        <h2 id="ch16">16. 扫码报工</h2>
        <p>这是员工最高频的操作，整个流程不超过 30 秒。</p>

        <h3>16.1 操作流程</h3>
        <ol class="step-list">
          <li>点击首页 <strong>「扫码报工」</strong> 或底部导航 <strong>「报工」</strong></li>
          <li>扫描任务二维码，系统自动识别任务</li>
          <li>输入<strong>合格数</strong>和<strong>不良数</strong>（合计不超过派工数）</li>
          <li>上传完工照片（1-5张）或视频（最长30秒）</li>
          <li>点击 <strong>「提交」</strong>，立即显示预估工资</li>
        </ol>

        <div class="callout callout-warning">
          <div class="callout-title">注意事项</div>
          数据要真实准确。照片要清晰展示产品。提交后不可修改，被驳回可重新报工。
        </div>

        <!-- CH17: 工资与考勤 -->
        <h2 id="ch17">17. 工资与考勤</h2>

        <h3>17.1 查看工资</h3>
        <p><strong>路径</strong>：我的 → 工资</p>
        <p>选择月份查看计件工资、补贴、扣款、实发金额。可查看每笔报工的工序明细。</p>

        <h3>17.2 电子工资条</h3>
        <p><strong>路径</strong>：我的 → 工资条</p>
        <p>查看完整工资明细，支持电子签名确认或拒绝（提交异议）。支持 PDF 下载。</p>

        <h3>17.3 考勤打卡</h3>
        <p><strong>路径</strong>：首页「打卡」或 我的 → 考勤打卡</p>
        <p>上班签到、下班签退，系统记录工作时长。忘记打卡可申请补卡（需班组长审批）。</p>

        <!-- CH18: 客户下单 -->
        <h2 id="ch18">18. 客户下单</h2>

        <h3>18.1 下单流程</h3>
        <ol class="step-list">
          <li>底部导航 <strong>「下单」</strong>，浏览产品列表</li>
          <li>点击产品，选择型号（颜色、材料、规格）</li>
          <li>输入订单数量、交期（建议至少7天后）、备注</li>
          <li>点击 <strong>「提交订单」</strong>，确认后订单进入系统</li>
        </ol>
        <div class="callout callout-info">
          <div class="callout-title">修改规则</div>
          草稿状态可修改。已确认后不可修改，需联系客服或作废重建。
        </div>

        <!-- CH19: 订单追踪 -->
        <h2 id="ch19">19. 订单追踪</h2>
        <p><strong>路径</strong>：底部导航「追踪」或订单详情「查看进度」</p>
        <p>时间线视图显示各工序完成状态（已完成/进行中/待开始），每2分钟自动刷新。</p>

        <h3>19.1 对账单</h3>
        <p><strong>路径</strong>：我的 → 对账单</p>
        <p>按月查看对账明细，核对金额，支持下载 PDF、确认对账、提出异议。</p>

        <!-- CH20: 常见问题 -->
        <h2 id="ch20">20. 常见问题</h2>

        <h3>Q: 订单确认后发现型号错了？</h3>
        <p>已确认的订单不可修改。操作：<strong>作废该订单 → 新建正确的订单</strong>。</p>

        <h3>Q: 报工提交后发现数字填错了？</h3>
        <p>联系班组长 <strong>「驳回」</strong> 该报工，然后重新报工。</p>

        <h3>Q: 工资计算有误？</h3>
        <p>进入工资管理查看明细，每笔报工的数量和金额都有记录。如有误，通知财务调整。</p>

        <h3>Q: 物料不足能排产吗？</h3>
        <p>排产前系统会提示不齐套。建议等物料到货或紧急采购，不建议强行排产。</p>

        <h3>Q: 忘记打卡怎么办？</h3>
        <p>进入考勤页面申请补卡，填写原因，等班组长审批。</p>

        <h3>Q: 员工端和客户端有什么区别？</h3>
        <table class="doc-table">
          <thead><tr><th>功能</th><th>员工端</th><th>客户端</th></tr></thead>
          <tbody>
            <tr><td>查看任务</td><td>✅</td><td>—</td></tr>
            <tr><td>扫码报工</td><td>✅</td><td>—</td></tr>
            <tr><td>查看工资</td><td>✅</td><td>—</td></tr>
            <tr><td>客户下单</td><td>—</td><td>✅</td></tr>
            <tr><td>订单进度</td><td>—</td><td>✅</td></tr>
            <tr><td>对账单</td><td>—</td><td>✅</td></tr>
          </tbody>
        </table>

        <!-- CH21: 模具管理 -->
        <h2 id="ch21">21. 模具管理</h2>
        <p>模具管理覆盖模具全生命周期：档案登记、保养计划、保养执行记录、工序绑定。</p>

        <h3>21.1 模具档案</h3>
        <p><strong>操作路径</strong>：生产 → 模具管理</p>
        <ol class="step-list">
          <li>点击 <strong>「+ 新建模具」</strong></li>
          <li>填写模具编码（唯一）、名称、类型（冲压/注塑/压铸等）、状态（启用/停用）</li>
          <li>设置预计寿命（总次数），系统自动计算剩余寿命百分比</li>
          <li>上传模具照片或图纸附件</li>
        </ol>

        <h3>21.2 保养管理</h3>
        <p><strong>操作路径</strong>：模具详情 → 保养记录</p>
        <ol class="step-list">
          <li>点击 <strong>「+ 新建保养」</strong></li>
          <li>选择保养类型：日保养/一级保养/二级保养/大修/维修</li>
          <li>填写保养内容、执行人、结果（正常/异常）</li>
          <li>保存后记入模具保养履历</li>
        </ol>

        <h3>21.3 工序绑定</h3>
        <p><strong>操作路径</strong>：模具详情 → 工序绑定</p>
        <ol class="step-list">
          <li>勾选该模具可用于的工序（支持多选）</li>
          <li>保存后，报工时可选关联模具</li>
        </ol>
        <div class="callout callout-info">
          <div class="callout-title">提示</div>
          模具寿命接近上限时，系统将在首页和看板中预警提示。
        </div>

        <!-- CH22: 质检模板与缺陷代码 -->
        <h2 id="ch22">22. 质检模板与缺陷代码</h2>

        <h3>22.1 质检模板</h3>
        <p><strong>操作路径</strong>：生产 → 质检模板</p>
        <ol class="step-list">
          <li>点击 <strong>「+ 新建模板」</strong></li>
          <li>填写模板名称，选择适用工序</li>
          <li>添加质检项目，支持三种类型：
            <ul>
              <li><strong>合格/不合格</strong>：二值判定，勾选即通过</li>
              <li><strong>测量值</strong>：填入实测数值，可设上下限</li>
              <li><strong>文本</strong>：填写检测备注</li>
            </ul>
          </li>
          <li>保存后可在报工审核时引用模板进行质检</li>
        </ol>

        <h3>22.2 缺陷代码</h3>
        <p><strong>操作路径</strong>：生产 → 缺陷代码</p>
        <ol class="step-list">
          <li>点击 <strong>「+ 新建缺陷」</strong></li>
          <li>填写缺陷编码（唯一）、名称、描述</li>
          <li>选择严重程度：轻微/一般/严重/致命</li>
          <li>保存后可在报工或质检时快速标记缺陷原因</li>
        </ol>
        <div class="callout callout-success">
          <div class="callout-title">最佳实践</div>
          将常见缺陷提前录入缺陷代码库，质检时直接选择，减少手动输入，便于后续统计分析。
        </div>

        <!-- CH23: 审批流程配置 -->
        <h2 id="ch23">23. 审批流程配置</h2>
        <p>系统支持自定义审批流程，不再局限于固定的两级审核。可针对订单确认、报工审核、工资结算等不同场景配置独立的审批步骤。</p>

        <h3>23.1 新建流程</h3>
        <p><strong>操作路径</strong>：系统 → 审批流程</p>
        <ol class="step-list">
          <li>点击 <strong>「+ 新建流程」</strong></li>
          <li>填写流程名称，选择触发场景（订单/报工/工资等）</li>
          <li>按顺序添加审核步骤：
            <ul>
              <li>选择审核角色（班组长/质检/厂长/财务等）</li>
              <li>可选设置审核人（指定具体人员）</li>
              <li>设置步骤标签（如"班组长初审""质检终审"）</li>
            </ul>
          </li>
          <li>保存后，对应场景将按配置的流程执行审核</li>
        </ol>

        <h3>23.2 流程匹配规则</h3>
        <p>系统按触发场景匹配对应的审批流程。如未配置，则使用默认流程（班组长初审 → 质检终审）。</p>
        <div class="callout callout-info">
          <div class="callout-title">灵活适配</div>
          不同场景可配置不同的审批流程。例如：订单确认只需厂长审批，报工需要班组长+质检两级，工资结算需要厂长+财务两级。
        </div>

        <!-- CH24: 排班管理 -->
        <h2 id="ch24">24. 排班管理</h2>
        <p><strong>操作路径</strong>：生产 → 排班管理</p>

        <h3>24.1 班次规则</h3>
        <ol class="step-list">
          <li>点击 <strong>「+ 新建班次」</strong></li>
          <li>填写班次名称（如"白班""夜班"）、起止时间</li>
          <li>设置加班倍率（如夜班 1.5 倍）</li>
        </ol>

        <h3>24.2 员工排班</h3>
        <ol class="step-list">
          <li>选择排班月份</li>
          <li>在日历中点击日期，为员工分配班次</li>
          <li>支持批量排班：选中多日，统一分配班次</li>
          <li>保存后，系统自动统计员工出勤工时</li>
        </ol>
        <div class="callout callout-warning">
          <div class="callout-title">考勤关联</div>
          排班数据与考勤打卡联动：员工打卡时间与排班班次对比，自动识别迟到/早退/缺勤。
        </div>

        <!-- CH25: 时薪管理 -->
        <h2 id="ch25">25. 时薪管理</h2>
        <p>适合非计件岗位（如质检员、仓管员、机修工），按时薪计算工资。</p>
        <p><strong>操作路径</strong>：生产 → 时薪管理</p>

        <h3>25.1 设置时薪标准</h3>
        <ol class="step-list">
          <li>选择员工</li>
          <li>设置基础时薪（元/小时）</li>
          <li>可选设置加班倍率：平日 1.5 倍、周末 2 倍、节假日 3 倍</li>
          <li>保存后自动生效</li>
        </ol>

        <h3>25.2 工资计算</h3>
        <p><strong>公式</strong>：<code>月工资 = Σ(工时 × 时薪 × 加班倍率)</code></p>
        <ol class="step-list">
          <li>系统从考勤打卡和排班数据自动计算工时</li>
          <li>按设置的时薪标准和加班倍率自动算薪</li>
          <li>支持手动添加补贴或扣款</li>
          <li>与计件工资在同一工资表中汇总展示</li>
        </ol>

        <!-- CH26: 外协管理 -->
        <h2 id="ch26">26. 外协管理</h2>
        <p>管理外协加工流程：创建外协订单 → 外协报工 → 对账结算。</p>

        <h3>26.1 外协订单</h3>
        <p><strong>操作路径</strong>：外协 → 外协订单</p>
        <ol class="step-list">
          <li>点击 <strong>「+ 新建外协订单」</strong></li>
          <li>选择外协供应商、产品型号、数量、交期</li>
          <li>确认后外协订单生效</li>
        </ol>

        <h3>26.2 外协报工</h3>
        <p><strong>操作路径</strong>：外协 → 外协报工</p>
        <ol class="step-list">
          <li>选择外协订单，录入合格数/不良数</li>
          <li>可上传外协完工照片作为凭证</li>
          <li>提交后等待内部审核</li>
        </ol>

        <h3>26.3 外协对账</h3>
        <p><strong>操作路径</strong>：外协 → 外协对账</p>
        <ol class="step-list">
          <li>系统按审核通过的外协报工自动汇总</li>
          <li>支持导出对账单与供应商核对</li>
          <li>对账确认后进入付款流程</li>
        </ol>

        <!-- CH27: 出货管理 -->
        <h2 id="ch27">27. 出货管理</h2>
        <p><strong>操作路径</strong>：仓储 → 出货管理</p>

        <h3>27.1 创建出货单</h3>
        <ol class="step-list">
          <li>点击 <strong>「+ 新建出货单」</strong></li>
          <li>选择客户和关联订单（支持多订单合并出货）</li>
          <li>逐条填写出货产品、型号、数量</li>
          <li>保存后库存自动扣减</li>
        </ol>

        <h3>27.2 发货跟踪</h3>
        <ol class="step-list">
          <li>填写物流单号、承运商</li>
          <li>系统记录发货时间，订单状态自动更新为「已发货」</li>
          <li>客户在手机端可查看物流信息</li>
        </ol>

        <h3>27.3 签收确认</h3>
        <ol class="step-list">
          <li>客户在手机上确认签收</li>
          <li>可选上传签收回单照片</li>
          <li>签收后出货单完成，订单进入「已完成」状态</li>
        </ol>

        <!-- CH28: AI 智能中心 -->
        <h2 id="ch28">28. AI 智能中心</h2>
        <p>AI 智能中心是 辰科MES 内置的智能化能力集合，基于工厂真实数据提供分析、预警、辅助操作。</p>

        <h3>28.1 数据预警</h3>
        <p><strong>操作路径</strong>：AI 智能中心 → 数据预警</p>
        <ol class="step-list">
          <li>系统自动监控产能负荷、良率趋势、交期倒计时等指标</li>
          <li>异常时在首页和预警中心同时推送</li>
          <li>支持配置预警规则（如良率低于 90% 报警）</li>
          <li>预警列表显示类型、等级、内容和建议操作</li>
        </ol>

        <h3>28.2 AI 照片计数</h3>
        <p>在扫码报工时，上传完工照片后点击 <strong>「AI 计数」</strong>，系统自动识别照片中的产品数量并填入合格数，减少手动输入。</p>

        <h3>28.3 AI 缺陷分类</h3>
        <p>在报工填写不良数时，上传不良品照片后点击 <strong>「AI 识别缺陷」</strong>，系统自动判断缺陷类型（如划痕/变形/色差等），辅助质检决策。</p>

        <h3>28.4 语音报工</h3>
        <p>在报工页面点击 <strong>「语音输入」</strong> 按钮，通过手机麦克风语音输入合格数和不良数（如"合格一百五十，不良两个"），系统自动解析填入对应字段，双手不离开工件。</p>

        <div class="callout callout-success">
          <div class="callout-title">提示</div>
          AI 照片计数和缺陷分类需要上传清晰的产品照片。语音报工使用系统自带语音识别能力。
        </div>

        <!-- CH29: SPC 质量图表 -->
        <h2 id="ch29">29. SPC 质量图表</h2>
        <p>SPC（统计过程控制）用于实时监控生产过程中的质量波动，提前发现异常趋势。</p>
        <p><strong>操作路径</strong>：生产 → SPC 图表</p>

        <h3>29.1 Xbar-R 控制图</h3>
        <ol class="step-list">
          <li>选择产品型号和工序</li>
          <li>选择时间范围</li>
          <li>系统自动计算均值（Xbar）和极差（R），绘制控制图</li>
          <li>超出控制限的数据点自动标红，提示异常</li>
        </ol>

        <h3>29.2 工序能力分析（CPK）</h3>
        <ol class="step-list">
          <li>基于历史质检测量值自动计算 CPK 值</li>
          <li>CPK ≥ 1.33 表示工序能力充足</li>
          <li>CPK &lt; 1.0 表示工序能力不足，需工艺改进</li>
        </ol>

        <div class="callout callout-info">
          <div class="callout-title">质量控制</div>
          定期查看 SPC 图表，及时发现工序偏移趋势，在出现不良品前采取纠正措施。
        </div>

        <!-- FOOTER -->
        <div class="doc-footer">
          <a href="#" @click.prevent="go('/')">
            <span class="label">← 返回</span>
            <span class="title">辰科MES 首页</span>
          </a>
          <a href="#ch1" @click.prevent="scrollToSection('ch1')">
            <span class="label">回到顶部</span>
            <span class="title">开始阅读</span>
          </a>
        </div>
      </main>
    </div>
  </div>
</template>

<style scoped>
/* NAV */
.doc-nav {
  position: fixed; top: 0; left: 0; right: 0; z-index: 100; height: 64px;
  padding: 0 2rem; display: flex; align-items: center; justify-content: space-between;
  background: rgba(255,255,255,.95); backdrop-filter: blur(16px);
  border-bottom: 1px solid #e2e8f0;
}
.doc-nav-logo { display: flex; align-items: center; gap: .6rem; font-size: 1.15rem; font-weight: 700; cursor: pointer; color: #0f172a; }
.doc-nav-logo-icon { width: 32px; height: 32px; border-radius: 8px; background: linear-gradient(135deg, #0891b2, #06b6d4); color: #fff; display: flex; align-items: center; justify-content: center; font-size: .7rem; font-weight: 800; }
.doc-nav-links { display: flex; gap: 1.5rem; align-items: center; }
.doc-nav-links a { font-size: .9rem; font-weight: 500; color: #475569; transition: color .2s; cursor: pointer; }
.doc-nav-links a:hover { color: #0f172a; }
.doc-nav-links .active { color: #0891b2; font-weight: 600; }

/* LAYOUT */
.doc-layout { display: flex; max-width: 1200px; margin: 0 auto; padding: 64px 2rem 4rem; gap: 2rem; }

/* SIDEBAR */
.doc-sidebar { width: 240px; flex-shrink: 0; position: sticky; top: 80px; align-self: flex-start; max-height: calc(100vh - 100px); overflow-y: auto; }
.doc-sidebar a {
  display: block; padding: .45rem .75rem; border-radius: 6px;
  font-size: .85rem; color: #475569; transition: all .15s;
  margin-bottom: 2px; cursor: pointer;
}
.doc-sidebar a:hover { background: #f1f5f9; color: #0f172a; }
.doc-sidebar a.active { background: #dbeafe; color: #0891b2; font-weight: 600; }
.doc-sidebar .group { margin-bottom: 1.5rem; }
.doc-sidebar .group-title { font-size: .7rem; font-weight: 700; text-transform: uppercase; letter-spacing: .08em; color: #94a3b8; padding: .5rem .75rem .25rem; }

/* CONTENT */
.doc-content { flex: 1; min-width: 0; max-width: 780px; }
.doc-content h1 { font-size: 2rem; font-weight: 800; margin-bottom: .5rem; letter-spacing: -.01em; color: #0f172a; }
.doc-content .doc-subtitle { font-size: 1.1rem; color: #475569; margin-bottom: 2.5rem; line-height: 1.7; }
.doc-content h2 { font-size: 1.5rem; font-weight: 700; margin: 3rem 0 1rem; padding-top: 1rem; border-top: 1px solid #e2e8f0; color: #0f172a; }
.doc-content h2:first-of-type { border-top: none; padding-top: 0; }
.doc-content h3 { font-size: 1.15rem; font-weight: 700; margin: 2rem 0 .75rem; color: #0f172a; }
.doc-content p { margin-bottom: 1rem; color: #475569; line-height: 1.7; }
.doc-content ul, .doc-content ol { margin-bottom: 1rem; padding-left: 1.5rem; color: #475569; }
.doc-content li { margin-bottom: .4rem; line-height: 1.7; }
.doc-content strong { color: #0f172a; font-weight: 600; }

/* CALLOUT */
.callout { padding: 1rem 1.25rem; border-radius: 12px; margin-bottom: 1.5rem; font-size: .9rem; }
.callout-info { background: #eff6ff; border-left: 3px solid #3b82f6; color: #1e40af; }
.callout-success { background: #f0fdf4; border-left: 3px solid #22c55e; color: #166534; }
.callout-warning { background: #fffbeb; border-left: 3px solid #f59e0b; color: #92400e; }
.callout-title { font-weight: 700; margin-bottom: .25rem; }

/* STEP LIST */
.step-list { counter-reset: step; list-style: none; padding: 0; margin-bottom: 1.5rem; }
.step-list li { counter-increment: step; padding: .75rem 0 .75rem 3rem; position: relative; border-bottom: 1px solid #e2e8f0; color: #475569; }
.step-list li:last-child { border-bottom: none; }
.step-list li::before {
  content: counter(step); position: absolute; left: 0; top: .75rem;
  width: 28px; height: 28px; border-radius: 50%;
  background: #0891b2; color: #fff;
  display: flex; align-items: center; justify-content: center;
  font-size: .8rem; font-weight: 700;
}

/* TABLE */
.doc-table { width: 100%; border-collapse: collapse; margin-bottom: 1.5rem; font-size: .9rem; }
.doc-table th { background: #f1f5f9; padding: .6rem .8rem; text-align: left; font-weight: 600; border: 1px solid #e2e8f0; color: #0f172a; }
.doc-table td { padding: .6rem .8rem; border: 1px solid #e2e8f0; color: #475569; }
.doc-table tr:hover td { background: #f8fafc; }

/* CODE */
code { background: #f1f5f9; padding: .15rem .4rem; border-radius: 4px; font-size: .85em; font-family: 'SF Mono', 'Fira Code', monospace; }

/* MOBILE TOC */
.mobile-toc { display: none; margin-bottom: 2rem; }
.mobile-toc select { width: 100%; padding: .6rem; border: 1px solid #e2e8f0; border-radius: 6px; font-size: .9rem; background: #fff; }

/* FOOTER */
.doc-footer { display: flex; justify-content: space-between; margin-top: 4rem; padding-top: 2rem; border-top: 1px solid #e2e8f0; }
.doc-footer a { display: flex; flex-direction: column; padding: 1rem 1.5rem; border: 1px solid #e2e8f0; border-radius: 12px; transition: all .2s; min-width: 200px; cursor: pointer; }
.doc-footer a:hover { border-color: #0891b2; box-shadow: 0 1px 3px rgba(0,0,0,.06); }
.doc-footer .label { font-size: .75rem; color: #94a3b8; margin-bottom: .25rem; }
.doc-footer .title { font-size: .95rem; font-weight: 600; color: #0891b2; }

@media (max-width: 900px) {
  .doc-nav { padding: 0 1rem; }
  .doc-nav-links { gap: 1rem; }
  .doc-nav-links a { font-size: .8rem; }
  .doc-sidebar { display: none; }
  .mobile-toc { display: block; }
  .doc-layout { padding: 64px 1rem 2rem; }
  .doc-content h1 { font-size: 1.5rem; }
  .doc-content h2 { font-size: 1.25rem; }
  .doc-footer { flex-direction: column; gap: 1rem; }
  .doc-footer a { min-width: auto; }
}
</style>
