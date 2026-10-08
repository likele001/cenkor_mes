# AI 报工视觉助手（mes_ai_vision）扩展说明

> 版本：1.0.0 ｜ 作者：Cenkor ｜ 类别：AI
> 适用：cenkormes 独立版 MES（FastAPI + 扩展宿主）

---

## 一、功能简介

面向一线报工场景的 AI 增值扩展，接视觉大模型（OpenAI 兼容多模态，如 MiniMax M3）：

| 功能 | 说明 |
|---|---|
| **AI 拍照计数** | 上传批量零件照片，AI 识别重叠/堆叠零件数量并给出总计数、置信度、分张明细 |
| **AI 缺陷分类** | 上传不良品照片，AI 自动从宿主「缺陷代码表（defect_codes）」中匹配缺陷类型与严重程度 |

特点：
- **零第三方依赖**：HTTP 调用走标准库 urllib，不依赖 openai/httpx 库，任何宿主环境可直接运行
- **随宿主热挂载**：安装后重启生效；走应用中心安装则热挂载免重启
- **可插拔**：卸载保留业务数据（`ext_ai_config` 配置表），重装自动恢复
- **权限受控**：新权限 `ext.ai.report`（AI 报工视觉），自动注入 admin 角色，可用 RBAC 管控

---

## 二、扩展包结构

```
mes_ai_vision-1.0.0.zip
├── manifest.json          # 清单：key/名称/版本/权限/菜单
├── router.py              # 路由 + 业务逻辑（单文件，不支持相对导入）
├── migrations.sql         # 建表 ext_ai_config + 幂等种子
└── frontend/
    └── plugin.js          # 管理端「AI 报工助手」页面（Vue 运行时由宿主注入）
```

挂载路径前缀：`/api/extensions/mes_ai_vision/`

---

## 三、安装

### 方式 A：本地直装（测试/开发）

1. 将 zip 解压到扩展目录：

```bash
cd /www/wwwroot/cenkormes/backend
unzip /root/dev/mes_ai_vision-1.0.0.zip -d extensions/mes_ai_vision
```

2. 重启 cenkormes 后端（宝塔面板重启，避免与面板操作冲突请人工执行）。

3. 验证挂载：

```bash
curl http://127.0.0.1:8500/api/extensions/mes_ai_vision/ping -H "Authorization: Bearer <admin-token>"
# 返回 {"code":200,"data":{"ok":true,"extension":"mes_ai_vision"}}
```

### 方式 B：应用中心 / 功能市场（正式分发）

1. 将 zip 上传到 Cenkor 门户 hub（admin.cenkor.cn）→ 提交审核 → 定价 → 上架；
2. 租户在 cenkormes 后台「功能市场」中一键下载安装（宿主自动热挂载，**免重启**）；
3. license 授权通过后生效；到期自动停用（授权门控）。

> 说明：未绑定 hub / 未配置 license 时，扩展以 `local` 状态运行（本地直装可用）；绑定后由授权快照门控。

---

## 四、配置（必读）

### 4.1 MiniMax key（在管理端页面填写）

重启后，管理端左侧菜单出现 **「AI 报工助手」**，进入页面：
- Base URL：`https://api.minimax.cn/v1`（OpenAI 兼容，默认已填）
- API Key：填入你的 MiniMax 密钥（49 元/M3 套餐支持视觉）
- 模型 ID：`MiniMax-M3`（默认已填）
- 超时：`120` 秒

点击「保存设置」即写入 `ext_ai_config` 表（key 脱敏显示）。

### 4.2 ⚠️ 公网地址配置（必需，否则 AI 拉不到图）

扩展把图片地址发给 MiniMax 时，需要**公网可访问的完整 URL**。相对路径 `/api/files/{id}` 会拼接宿主 `PUBLIC_BASE_URL`。

当前 cenkormes `.env` 配置：

```ini
PUBLIC_BASE_URL=http://localhost:8500   # ❌ 必须改
```

请改为正式公网域名（可被互联网访问）：

```ini
PUBLIC_BASE_URL=https://你的公网域名
```

> 若仍为 `localhost`：前端上传图片拿到的是 `/api/files/{id}` 相对地址，扩展将返回 503「无法为图片生成公网地址」并给出提示。
> 若直接传入完整公网 URL（http/https 开头），则不受此限制。

---

## 五、接口文档

统一响应格式：`{ "code": 200, "msg": "", "data": {...} }`（业务码：200 成功 / 401 未登录 / 403 无权限 / 503 网关未配置或地址不可达 / 502 模型调用失败）

### 5.1 `POST /api/extensions/mes_ai_vision/photo-count`

拍照自动计数。

请求体：

```json
{
  "image_urls": ["/api/files/12", "/api/files/13"],
  "hint": "这批零件大概 200 个左右"
}
```

| 字段 | 必填 | 说明 |
|---|---|---|
| image_urls | 是 | 图片地址，最多 6 张；`/api/files/{id}` 或完整公网 URL |
| hint | 否 | 员工提示（数量预估等），辅助识别 |

响应 `data`：

```json
{
  "ok": true,
  "count": 186,
  "confidence": "high",
  "per_image": [120, 66],
  "note": "1 号图 120 件，2 号图 66 件（底部有遮挡按比例估算）",
  "reply": "（模型原始回复）",
  "structured": { "...": "..." },
  "image_count": 2,
  "tokens_in": 1280,
  "tokens_out": 86
}
```

### 5.2 `POST /api/extensions/mes_ai_vision/defect-classify`

AI 缺陷自动分类（复用宿主 `defect_codes` 表，仅取 `is_active=1`）。

请求体：

```json
{
  "image_urls": ["/api/files/15"],
  "remark": "表面有毛刺"
}
```

响应 `data`：

```json
{
  "ok": true,
  "defect_code_id": 3,
  "defect_code": "SCRATCH",
  "defect_name": "划伤",
  "severity": "major",
  "confidence": "medium",
  "description": "表面可见线性划痕，长度约 15mm，判定为划伤",
  "options_count": 12
}
```

> 若宿主未维护缺陷代码，返回 `ok:false, error:"未配置缺陷代码…"`。

### 5.3 `GET /api/extensions/mes_ai_vision/config`

读取配置（API Key 脱敏）与公网 base 状态。

### 5.4 `POST /api/extensions/mes_ai_vision/config`

保存配置：

```json
{
  "gateway_base_url": "https://api.minimax.cn/v1",
  "gateway_api_key": "sk-xxxx",
  "model_id": "MiniMax-M3",
  "timeout_seconds": "120"
}
```

### 5.5 `GET /api/extensions/mes_ai_vision/ping`

存活检查（无需业务权限，仍须登录）。

---

## 六、使用操作（管理端）

1. 登录 cenkormes 管理后台 → 左侧菜单 **「AI 报工助手」**；
2. 先填好 4.1 的模型配置并保存；
3. **上传图片**（本地上传，自动填入地址）或**粘贴图片地址**（每行一个）；
4. 可选填「计数提示」/「缺陷备注」；
5. 点击 **「AI 拍照计数」** 或 **「AI 缺陷分类」**，等待识别结果展示。

> 员工端（H5/小程序）若已集成扩展接口，可直接在报工流程中调用上述接口实现拍照计数/缺陷分类自动填充。

---

## 七、卸载

```bash
rm -rf /www/wwwroot/cenkormes/backend/extensions/mes_ai_vision
```

- 重启后宿主不再挂载该扩展；
- `ext_ai_config` 表数据保留（幂等设计，重装自动恢复），如需彻底清除可手动 `DROP TABLE ext_ai_config;`

---

## 八、常见问题

| 问题 | 原因 | 解决 |
|---|---|---|
| `503 无法为图片生成公网地址` | `PUBLIC_BASE_URL` 为 localhost 且传了相对地址 | 改 `.env` 公网域名 / 传完整公网 URL |
| `503 AI 网关未配置` | 未保存 key | 后台「AI 报工助手」填写并保存 |
| `502 视觉模型返回 401 login fail` | API Key 无效/过期 | 核对 MiniMax 密钥 |
| `403 无权限` | 账号缺 `ext.ai.report` | admin 角色已自动注入；自定义账号在角色管理勾选 |
| 菜单不显示 | 未重启 / 扩展未挂载 | 重启后端或走应用中心安装 |
| 缺陷分类提示"未配置缺陷代码" | 宿主 `defect_codes` 表无启用项 | 先维护「质量管理 → 缺陷代码」 |

---

## 九、测试记录（路线 A）

在服务器生产同款 venv（`/www/server/pyporject_evn/cenkormes/bin/python3.13`）中执行 `test_install.py`，结果 7/7 通过：

- 解压安装 → 宿主扫描挂载 ✓
- 迁移建表 `ext_ai_config` + 4 条种子 ✓
- 权限 `ext.ai.report` 注入 admin ✓
- `ping`（门控 local 放行）✓
- 配置读写 + key 脱敏 ✓
- 图片 URL 守卫（localhost base 拦截并提示）✓
- 真实请求到达 MiniMax 网关（无效 key 返回 401，链路通）✓

---

*本文件随扩展包一起维护；升级版本时同步更新文档。*
