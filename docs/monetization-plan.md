# CenkorMES 商业化与变现方案（Open-Core）

> 状态：规划草案 · 记录时间 2026-10-06
> 前提：本仓库为 AGPL-3.0 开源独立版（单租户私有部署）；配套商业 SaaS 版为 lightmes。

## 一、法律前提（决定玩法）
1. **AGPL 核心不可闭源**：主干代码一旦以 AGPL 开源，不能再收回为商业闭源。变现只能走 **open-core**——主干留 AGPL 公开仓，商业模块放独立私有仓（`cenkormes-pro`），通过 overlay 挂载。
2. **AGPL §13 网络条款**：即使只做 SaaS，网络用户也须能获取其所用 AGPL 代码（含修改）的源码。不能靠"藏源码"变现，卖的是 Pro 功能 + 托管 + 服务。
3. **CLA 缺口（风险）**：README 欢迎 PR 但无 Contributor License Agreement，社区贡献代码版权归贡献者，将来无法对其再授权/闭源。建议尽快上 CLA（如 CLA Assistant）或至少 DCO。

## 二、现有变现骨架
- `backend/app/core/edition.py`：`EDITION / IS_COMMUNITY / IS_PRO`，注释"安装时由 pro 覆盖"——已按 open-core 设计。
- `GET /api/admin/system/version` 返回 `edition` 字段——前端可据此门控 Pro 入口。
- `docs/cenkormes-vs-lightmes.html`：已划定 SaaS/Pro 独有项。
- `models/mold.py / spc.py / quotation.py`：**有表无路由**（半成品），天然 Pro 模块，补全即可。

## 三、商业功能清单（按性价比排序）
| 优先级 | Pro 模块 | 卖点 | 现状 |
|---|---|---|---|
| ★★★ | 报价/CPQ（成本核算→报价单→转工单） | 关联成交 | 模型已有 |
| ★★★ | SPC 统计过程控制（控制图/Cpk/预警） | 汽车/电子刚需 | 模型已有 |
| ★★★ | 模具管理（寿命/保养/领用） | 注塑/五金刚需 | 模型已有 |
| ★★☆ | AI 员工/智能排产优化 | 差异化、难自研 | SaaS 独有可下放 |
| ★★☆ | 行业模板包（家具/五金/电子/注塑） | 开箱即用 | 需打包 |
| ★★☆ | 高级 BI/老板驾驶舱/自定义报表引擎 | 决策层付费 | 基于 exec_dashboard |
| ★☆☆ | 多工厂/多组织 | 独立版单租户天然 Pro | 需设计 |
| ★☆☆ | 可配置审批流引擎 | 流程设计器 | approval 半成品升级 |

**非代码变现（更稳）**：托管/私有云部署（运维+备份+升级+SLA）、支持订阅（优先修复/安全补丁/实施培训）、硬件与系统集成（ERP 金蝶/用友、PDA/工控机/电子秤数采、标签/针式打印、钉钉企微深度）。不受 AGPL 约束。

## 四、技术落地：门控机制
1. 挂载点（开源仓，AGPL 干净）`app/api/router.py` 末尾：
   ```python
   from app.core.edition import IS_PRO
   if IS_PRO:                      # 社区版跳过；pro 包不存在也不报错
       from pro.api import pro_router
       api_router.include_router(pro_router, prefix="/admin/pro", dependencies=_admin_deps)
   ```
2. 私有 overlay 仓 `cenkormes-pro`：覆盖 `app/core/edition.py`（`IS_PRO=True`）+ 投放 `pro/` 包。开源仓永不含 `pro/`。
3. 前端：按 `/version` 的 `edition` lazy 加载 Pro 页面；Pro 页放独立私有前端包。
4. 授权激活：pro overlay 校验签名 license key（机器指纹 + 有效期），防拷贝滥用；轻量即可，不做重度 DRM。

## 五、建议路线
先跑通"开源仓 + pro overlay + 授权 + 前端门控"闭环：选「报价 CPQ」做第一个 Pro 模块（模型已有、变现最快），验证后再批量上 SPC/模具/AI。同时立刻补 CLA。

## 六、待办
- [ ] 补 CLA / 贡献者协议
- [ ] 搭 `IS_PRO` 挂载骨架 + `pro/` overlay 目录 + 授权脚手架
- [ ] 报价 CPQ 作为首个 Pro 模块（CRUD+路由+前端）
- [ ] 完善自托管用户升级流程（见 docs/DEPLOYMENT.md 升级章节）
