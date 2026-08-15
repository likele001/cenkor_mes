# CenkorMES × ck_crm 集成适配模块（crm_adapter）开发说明

## 1. 这个模块解决什么问题

ck_crm 是一个「通用集成中枢」：它用统一的 Connector 框架对接外部系统（MES/ERP/WMS/QMS/PLM/EAM）。
本模块让 **CenkorMES 作为其中一个「分支系统」** 接入 ck_crm，实现：

- CRM 把销售订单**推送**到 MES；
- MES 生产状态变化后**实时回传**给 CRM（CRM 订单状态随之更新）；
- 双向 **HMAC-SHA256 验签**，保证接口不被伪造。

模块完全独立（`app/integration/crm_adapter/`），不耦合 MES 其它业务表，开箱即用、自动建表。

## 2. 架构与数据流

```
ck_crm (中枢)                          CenkorMES (本模块 crm_adapter)
─────────────                         ───────────────────────────────
[管理员在 CRM 建「集成连接」]
      │  配置 base_url / api_key
      │
      │ POST /api/orders  (标准订单 + HMAC)
      ▼
   MES 收单 ──► 落库 crm_inbound_orders (以 order_code 为锚点)
      │
      │ MES 生产状态变更时主动回传
      │ POST /api/integration/webhook/{connection_id} (HMAC)
      ▼
   CRM 更新订单状态
```

- 推送方向：CRM → MES（`POST /api/orders`）
- 状态同步方向：MES → CRM（webhook 回传，**推荐，实时**）
- 可选：CRM 也可主动拉取（`GET /api/orders/{order_code}`）

## 3. 文件结构

```
app/integration/
├── __init__.py
└── crm_adapter/
    ├── __init__.py        # 导出 inbound_router / admin_router
    ├── models.py          # CrmAdapterConfig(单行) + CrmInboundOrder
    ├── schemas.py         # 请求/响应 Pydantic 模型(镜像 CRM SalesOrderDTO)
    ├── security.py        # HMAC sign / verify_inbound
    ├── client.py          # notify_crm_status (回传 CRM webhook)
    └── router.py          # 接口 + push_status_update 工具函数
```

## 4. 接口契约

### 4.1 入站（CRM 调用，无需登录，HMAC 验签）

- `POST /api/orders`
  - 请求头：`X-Timestamp`、`X-Signature`（见第 5 节）
  - 请求体（标准 SalesOrderDTO）：
    ```json
    {
      "order_code": "SO202501001",
      "customer_name": "某某客户",
      "items": [{"product_name": "A", "spec": "", "quantity": 10, "unit_price": 0}],
      "delivery_date": "2026-09-01",
      "remark": ""
    }
    ```
  - 响应：`{"code":200,"msg":"","data":{"id":"<MES内部单号>","order_code":"SO202501001"}}`
- `GET /api/orders/{order_code}`
  - 响应：`{"code":200,"msg":"","data":{"order_code":"SO202501001","status":"producing","found":true}}`

### 4.2 管理（需登录 + `setting.manage` 权限）

- `GET /api/crm-adapter/config` → 读取当前配置
- `PUT /api/crm-adapter/config` → 保存配置（body 见下）

### 4.3 健康检查

MES 全局已有 `GET /api/health`（返回 `{"code":200,"data":{"status":"ok"}}`）。
ck_crm 的「测试连接」会探测 `{base_url}/api/health`，直接复用即可，无需本模块额外实现。

## 5. 鉴权：HMAC-SHA256 双向验签（与 ck_crm 完全一致）

- 签名头：
  - `X-Timestamp`：当前 Unix 秒（字符串）
  - `X-Signature`：`HMAC_SHA256(api_key, "{X-Timestamp}.{原始请求体字符串}")` 的十六进制
- 验签（MES 收 CRM 请求时）：
  - 取**收到的原始 body 字符串**（不要重新序列化！）重算签名，`hmac.compare_digest` 比对；
  - 校验时间戳在窗口内（默认 300 秒，可在配置 `sign_window` 调整）。
- 回传（MES 调 CRM webhook 时）：用**自己要发送的 body 字符串**算同样的签名带上。
- `api_key` 即 CRM 连接配置里填的共享密钥，两端必须一致。

> 代码见 `app/integration/crm_adapter/security.py`（`sign` / `verify_inbound`）。

## 6. 配置教程（对接 ck_crm）

1. 在 ck_crm 后台「集成连接」页新建一条连接：
   - 驱动类型选 `mes`；
   - `base_url` 填 **CenkorMES 的对外地址**（如 `https://ck.mes.cenkor.cn`，不要带末尾斜杠和 `/api`）；
   - `auth_type` 选 `hmac`，生成/填写 `api_key`（记下来）；
   - 保存后，连接列表里能看到该连接的 `id`（即 `{connection_id}` / CID）。
2. 在 CenkorMES 后台「系统 → CRM 对接配置」（对应 `PUT /api/crm-adapter/config`）填入：
   - `crm_base_url`：`https://crm.cenkor.cn`（ck_crm 对外地址）；
   - `connection_id`：第 1 步拿到的 CID；
   - `api_key`：第 1 步填写的共享密钥；
   - `enabled`: true；
   - `sign_window`: 300（按需）；
   - `status_map`：把 MES 内部状态名映射到 CRM 标准状态（见第 7 节）。
3. 在 ck_crm 该连接上点「测试连接」应返回成功（探测 MES 的 `/api/health`）。
4. 在 ck_crm 该连接上「推送订单」即可把销售订单推到 MES；MES 状态变更后实时回传。

## 7. 状态映射

CRM 标准状态只有 5 个：`pending`(待排产) / `producing`(生产中) / `part_done`(部分完工) / `completed`(已完成) / `cancelled`(已取消)。

两种做法（推荐第二种，零改代码）：

- 直接回传标准码：MES 调用回传时直接传上述 5 个字符串；
- 自定义状态名 + `status_map`：例如配置
  ```json
  {"待生产":"pending","生产中":"producing","已完工":"completed","已取消":"cancelled"}
  ```
  MES 回传自己的状态名，本模块自动翻译成标准码再发给 CRM。

## 8. 如何把 MES 真实订单状态接到回传

在 MES 自身订单状态变更的业务代码里，调用本模块提供的工具函数即可：

```python
from app.integration.crm_adapter.router import push_status_update
from app.core.db import SessionLocal

def on_production_status_change(order_code: str, mes_status: str):
    db = SessionLocal()
    try:
        # 更新本地 CRM 推送订单记录，并按 status_map 回传 CRM
        push_status_update(db, order_code, mes_status)
    finally:
        db.close()
```

- `order_code` 必须是 CRM 推送过来的业务单号（锚点）；
- `mes_status` 可以是标准码，也可以是 `status_map` 里的自定义名；
- 回传为「尽力而为」：网络/配置异常只记日志，不抛异常、不阻塞 MES 主业务。

如果你希望 CRM 也能主动来拉状态（而非 MES 推），`GET /api/orders/{order_code}` 已就绪，CRM 连接开启轮询即可。

## 9. 数据表

模块首次启动（且 `DB_AUTO_CREATE=true`）会自动建两张表：

- `crm_adapter_config`：单行配置（id=1）；
- `crm_inbound_orders`：CRM 推送进来的订单（含 `order_code` 唯一索引、`status`）。

## 10. 部署与生效

- 改完后端代码后，在面板**重启 CenkorMES 后端（8500）** 使模块生效；
- 路由会自动注册，无需改 nginx；
- ck_crm 侧若之前推送过，记得也在面板重启使「ensure_ascii 签名修复」生效。

## 11. 已知约定 / 坑

- ck_crm 早期版本推送时签名与线路 body 编码不一致（中文会验签失败）；该问题已在 ck_crm `connectors/mes.py` 修复（发送改为 `content=body_json`），请确保 ck_crm 已更新到修复版本。
- 本模块入站验签使用**原始请求体**重算，天然兼容上述修复，无需特殊处理。
