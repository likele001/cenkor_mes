---
kind: error_handling
name: 后端错误处理体系：BizError + FastAPI 全局异常处理器
category: error_handling
scope:
    - '**'
source_files:
    - backend/app/core/errors.py
    - backend/app/core/response.py
    - backend/app/core/middleware.py
    - backend/app/main.py
---

## 1. 使用的系统/方案

CenkorMES 后端基于 **FastAPI** 的异常处理机制，定义了一个轻量业务异常类 `BizError`，并在应用启动时注册了四个全局 `exception_handler`，将 HTTP 层、参数校验、业务异常与未捕获异常统一收敛为统一的 `{code, msg, data}` JSON 响应。

前端（admin / h5 / miniapp）通过统一的 HTTP 客户端封装（`frontend-admin-pro/src/utils/http.ts`、`frontend-h5/src/utils/http.ts`、`lightmes-miniapp/src/api/request.ts`）解析后端返回的 `code` 字段进行分支处理，未登录/鉴权失败等场景在前端侧拦截并跳转。

## 2. 关键文件

- `backend/app/core/errors.py` — 唯一自定义异常类型 `BizError(code: int, msg: str)`
- `backend/app/core/response.py` — 统一响应体 `ApiResponse` 及 `ok()` / `fail()` 构造器
- `backend/app/main.py` — FastAPI 应用入口，集中注册全部异常处理器
- `backend/app/core/middleware.py` — `SecurityHeadersMiddleware`（安全头中间件，非错误处理但属于请求/响应横切面）

## 3. 架构与约定

### 3.1 业务异常 `BizError`

```python
class BizError(Exception):
    def __init__(self, code: int, msg: str):
        self.code = code
        self.msg = msg
```

仅携带两个字段：业务码 `code` 与人类可读消息 `msg`。它被设计为在业务层抛出，由全局处理器转换为标准响应。

### 3.2 全局异常处理器（`main.py`）

| 处理器 | 捕获异常 | 行为 |
|---|---|---|
| `http_exception_handler` | `fastapi.HTTPException` | 将 `status_code` 放入 `code`，`detail` 放入 `msg`，**始终返回 HTTP 200** |
| `validation_exception_handler` | `RequestValidationError` | 固定 `code=400`，`msg="参数校验失败"`，`data.errors` 为 Pydantic errors 列表 |
| `biz_exception_handler` | `BizError` | 透传 `exc.code` 与 `exc.msg` |
| `any_exception_handler` | `Exception`（兜底） | 记录 `logger.error("未捕获异常: ...", exc_info=True)`；`dev` 环境额外返回 `error` 与 `type` 堆栈信息，生产环境仅返回 `code=500, msg="服务器错误"` |

所有处理器均返回 `JSONResponse(status_code=200, content=fail(...))`，即对外 HTTP 状态码恒为 200，真实状态语义由响应体中的 `code` 表达。

### 3.3 响应格式

`response.ok(data, msg)` 与 `response.fail(code, msg, data)` 生成形如：

```json
{"code": 200, "msg": "", "data": ...}
{"code": 404, "msg": "xxx不存在", "data": null}
```

这是前后端契约的统一错误协议。

### 3.4 路由层的实际用法

经搜索，当前代码库中 API 路由层**大量使用** `raise HTTPException(status_code=..., detail="...")`（例如审批流、字典、ERP 成本/凭证等模块），而**尚未发现**直接 `raise BizError(...)` 的使用点——说明 `BizError` 是预留的业务异常基类，现有路由仍依赖 FastAPI 原生 `HTTPException`，由 `http_exception_handler` 统一转译为 `{code, msg}` 格式。

### 3.5 前端侧的错误处理

三个前端项目各自维护一个 `utils/http.ts`（或 uni-app 的 `src/api/request.ts`），根据后端返回的 `code` 做分支：
- 200 → 正常数据
- 401/403 → 清除 token 并跳转登录
- 其他 → 弹出 `msg` 提示

这使错误呈现逻辑集中在前端 HTTP 拦截层，而非分散在各页面。

## 4. 约定与约束

- **对外 HTTP 状态码恒为 200**：所有 `exception_handler` 都显式 `status_code=200`，业务状态通过响应体 `code` 表达（`main.py` 中四个处理器一致实现）。
- **业务异常必须携带 `code` 与 `msg`**：`BizError.__init__` 强制要求这两个参数，无默认值。
- **未捕获异常在生产环境不泄露堆栈**：`any_exception_handler` 仅在 `settings.APP_ENV == "dev"` 时返回 `error` 与 `type` 字段，生产环境仅返回 `"服务器错误"`。
- **参数校验失败统一走 `RequestValidationError` 处理器**：所有 Pydantic 校验错误被聚合到 `data.errors` 数组，前端可逐字段展示。
- **安全相关响应头由中间件补充**：`SecurityHeadersMiddleware` 在 ASGI `send` 阶段注入 `X-Content-Type-Options`、`X-Frame-Options`、`Referrer-Policy`、`Permissions-Policy` 等头，且使用 `setdefault` 语义保留上游已有值。
- **CORS / TrustedHost 中间件按配置开关**：仅在 `settings.CORS_ORIGINS` / `settings.TRUSTED_HOSTS` 非空时启用，避免误开跨域。

## 5. 观察到的缺口

- `BizError` 目前未被任何业务路由使用，路由层仍散落 `raise HTTPException(...)`，未来可逐步迁移至 `BizError` 以获得更明确的业务语义。
- 没有统一的错误码枚举或常量表，`code` 值散落在各路由调用处（如 400、404、500），缺乏集中管理。