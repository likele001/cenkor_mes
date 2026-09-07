# 待开发：云存储独立 App 搬运（cenkor-admin → cenkormes）

> **状态**：待开发（本文档不实施任何代码改动，仅作为后续启动的开发蓝图）
> **拟完成时间**：客户咨询事项完成后启动
> **目标**：把 `cenkor-admin` 的 `cloud_storage` 完整 App 搬到 `cenkormes`，让 MES 也具备多云厂商统一接入 + 后台可切换 + 前端签名直传能力。

---

## 一、背景与动机

### 现状对比

| 项目 | 云存储形态 | driver 数 | 后台可切换 | 前端签名直传 | 凭据加密 |
|---|---|---|---|---|---|
| **cenkor-admin** | 独立 App（`apps/cloud_storage/`）| 6（阿里 OSS、腾讯 COS、七牛 Kodo、MinIO、又拍云、S3 基类）| ✅ | ✅ | ✅ AES-256-GCM |
| **cenkormes** | 内嵌模块（`app/storage/`）| 1（仅 LocalStorage，OSS/COS/Qiniu 字段空壳）| ❌ KV 持久化但 factory 写死 | ❌ | ❌ |

### 核心痛点

1. `cenkormes` 的 `factory.py` 三个函数（`get_active_storage` / `build_storage` / `get_storage_for`）**全部写死 `return LocalStorage()`**，后台切换 `storage_driver` 字段**不生效**。
2. **6 个真实 driver 全部缺失**，`.env` 里的 `ALIYUN_OSS_*` / `TENCENT_COS_*` / `QINIU_KODO_*` 只是空壳字段。
3. MES 业务强依赖附件（工单图、检验单、报工照片），**没有签名直传**意味着所有流量都走后端中转，**带宽 + 单点压力**。
4. **没有凭据加密**，客户拿到数据库即拿到 OSS AccessKey，安全合规风险高。
5. **没有迁移任务**——历史附件要从本地迁到云端时，只能手工拷。

---

## 二、目标与验收标准

### 功能目标

| 目标 | 验收标准 |
|---|---|
| 后台可切换 driver | 在「系统设置 → 云存储」菜单切换 provider 后，无需重启即生效（热加载） |
| 真实接入 4 大国内云 | 阿里 OSS / 腾讯 COS / 七牛 Kodo / 又拍云 至少 4 个 driver 真跑通 |
| 凭据加密 | DB 中所有 secret_key / access_key 以 AES-256-GCM 密文存储 |
| 前端签名直传 | H5 / 小程序拿到 `presign` 返回的临时 URL 直接上传到云，跳过后端中转 |
| 迁移任务 | 从 MinIO 迁到目标云的任务有状态字段、可查询进度、可失败重试 |
| 健康检查 | `GET /admin/cloud-storage/health` 校验当前激活 driver 是否连通 |

### 非功能目标

- 迁移方案兼容 **MySQL 5.7+** 与 **PostgreSQL 16**（cenkormes 当前 MySQL，cenkor-admin PG）
- 切换 driver **不重启服务**（依赖项解析 + 配置变更走事件总线）
- API 接口路径与 cenkor-admin **保持一致**（`/api/admin/cloud-storage/*`），便于两套系统共用前端 SDK
- 凭据密钥派生**复用现有 `SECRET_KEY`**（不引入新密钥管理方案，避免多套密钥混乱）

### 验收测试用例

1. **TC-01**：后台切换到 `aliyun`，上传一张图片，**DB 中 `storage_driver` 列值为 `aliyun`**，且**对象真实出现在阿里 OSS bucket**
2. **TC-02**：切换回 `local`，新上传图片**回到本地** `STORAGE_LOCAL_ROOT` 目录
3. **TC-03**：查看任意附件，**响应中 secret_key 为脱敏值**（`abc****xyz`）
4. **TC-04**：H5 调用 `/admin/cloud-storage/presign` 拿直传 URL → 用 PUT 直传到阿里 OSS → 后端回调成功 → 列表可查
5. **TC-05**：从 MinIO 迁移到腾讯 COS，迁移任务进度条更新到 `done`

---

## 三、详细范围

### 3.1 后端搬运清单（新建 `cenkormes/backend/app/cloud_storage/`）

| 源（cenkor-admin） | 目标（cenkormes） | 行数 | 适配点 |
|---|---|---|---|
| `apps/cloud_storage/__init__.py` | `app/cloud_storage/__init__.py` | 18 | 简化为导出 router（cenkormes 无 AppManifest 机制） |
| `apps/cloud_storage/manifest.py` | 不需要 | — | cenkormes 不走 manifest 注册 |
| `apps/cloud_storage/models.py` | `app/cloud_storage/models.py` | 51 | `Base` 改 `from app.models.base import Base` |
| `apps/cloud_storage/crypto.py` | `app/cloud_storage/crypto.py` | 39 | `settings.SECRET_KEY` 改 `from app.core.config import settings` |
| `apps/cloud_storage/router.py` | `app/cloud_storage/router.py` | 388 | `AsyncSession` 改 `from app.core.db import SessionLocal`；router 注入改 sync 风格 |
| `apps/cloud_storage/drivers/__init__.py` | `app/cloud_storage/drivers/__init__.py` | 47 | 直接搬运 |
| `apps/cloud_storage/drivers/_s3_base.py` | 同 | 181 | 直接搬运 |
| `apps/cloud_storage/drivers/aliyun.py` | 同 | 11 | 直接搬运 |
| `apps/cloud_storage/drivers/tencent.py` | 同 | 11 | 直接搬运 |
| `apps/cloud_storage/drivers/qiniu.py` | 同 | 21 | 直接搬运 |
| `apps/cloud_storage/drivers/minio.py` | 同 | 24 | 直接搬运 |
| `apps/cloud_storage/drivers/upyun.py` | 同 | 154 | 直接搬运 |

**预计总代码量**：约 **450-500 行 Python**。

### 3.2 数据库迁移脚本

新文件：`cenkormes/backend/alembic/versions/0005_cloud_storage.py`

```python
"""create cloud_storage_config and cloud_storage_migration_jobs

Revision ID: 0005_cloud_storage
Revises: 0004_erp_modules
Create Date: <TBD>
"""
revision = "0005_cloud_storage"
down_revision = "0004_erp_modules"

def upgrade():
    op.create_table(
        "cloud_storage_config",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("active_provider", sa.String(20), server_default="local"),
        sa.Column("creds_local", sa.Text, nullable=True),
        sa.Column("creds_tencent", sa.Text, nullable=True),
        sa.Column("creds_aliyun", sa.Text, nullable=True),
        sa.Column("creds_qiniu", sa.Text, nullable=True),
        sa.Column("creds_upyun", sa.Text, nullable=True),
        sa.Column("creds_minio", sa.Text, nullable=True),
        sa.Column("keep_local_backup", sa.Boolean, server_default=sa.true()),
        sa.Column("updated_by", sa.Integer, nullable=True),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_table(
        "cloud_storage_migration_jobs",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("source", sa.String(20), server_default="minio"),
        sa.Column("target", sa.String(20), nullable=False),
        sa.Column("total", sa.Integer, server_default="0"),
        sa.Column("done", sa.Integer, server_default="0"),
        sa.Column("failed", sa.Integer, server_default="0"),
        sa.Column("status", sa.String(20), server_default="pending"),
        sa.Column("error", sa.Text, nullable=True),
        sa.Column("started_at", sa.DateTime, nullable=True),
        sa.Column("finished_at", sa.DateTime, nullable=True),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
    )

def downgrade():
    op.drop_table("cloud_storage_migration_jobs")
    op.drop_table("cloud_storage_config")
```

> 字段差异：cenkormes 用**普通 DateTime**（无 timezone 字段），与现有 0001-0004 风格一致；新增 `creds_local` / `creds_minio` 两列（cenkor-admin 没有这两个）。

### 3.3 路由与菜单集成

| 改动位置 | 改动内容 |
|---|---|
| `backend/app/api/router.py` | 新增 `from app.cloud_storage.router import router as cloud_storage_router` + `api_router.include_router(cloud_storage_router, prefix="/admin/cloud-storage", dependencies=_admin_deps)` |
| `backend/app/core/startup.py`（或 main.py）| `ensure_permissions(["cloud_storage:read", "cloud_storage:write", "cloud_storage:admin"])` |
| `frontend-admin-pro/src/router/modules/system.ts` | 新增 `cloud-storage` 路由 |
| `frontend-admin-pro/src/locales/zh-CN.ts` + `en-US.ts` | 新增 `system.cloudStorage.*` 国际化 |
| `frontend-admin-pro/src/pages/system/CloudStoragePage.vue` | 搬运自 `cenkor-admin/.../CloudStorageView.vue`，适配 Element Plus 风格 |

### 3.4 接口契约（与 cenkor-admin 一致）

| 方法 | 路径 | 权限 | 说明 |
|---|---|---|---|
| GET | `/api/admin/cloud-storage/config` | cloud_storage:read | 读当前激活 provider + 脱敏凭据 |
| PUT | `/api/admin/cloud-storage/config/{provider}/creds` | cloud_storage:write | 设置 provider 凭据（AES加密入库） |
| DELETE | `/api/admin/cloud-storage/config/{provider}/creds` | cloud_storage:admin | 删除 provider 凭据 |
| POST | `/api/admin/cloud-storage/config/activate` | cloud_storage:admin | 切换激活 provider（热生效） |
| PUT | `/api/admin/cloud-storage/config` | cloud_storage:write | 改 keep_local_backup 等全局项 |
| GET | `/api/admin/cloud-storage/health` | cloud_storage:read | 检查当前 driver 连通性 |
| GET | `/api/admin/cloud-storage/files` | cloud_storage:read | 列出当前 bucket 对象 |
| DELETE | `/api/admin/cloud-storage/files` | cloud_storage:write | 删除对象 |
| POST | `/api/admin/cloud-storage/presign` | cloud_storage:write | 前端签名直传（PUT URL）|
| POST | `/api/admin/cloud-storage/migrate` | cloud_storage:admin | 启动迁移任务 |
| GET | `/api/admin/cloud-storage/migrate/{job_id}` | cloud_storage:read | 查询迁移进度 |

### 3.5 依赖与脚本变更

| 项 | 改动 |
|---|---|
| `backend/requirements.txt` | 新增 `aiobotocore>=2.5.0`（S3 协议通用）+ 已有的 `cryptography>=41.0` / `aiohttp>=3.9` 保留 |
| `backend/Dockerfile` | 镜像需 `pip install aiobotocore`，镜像体积约 +30MB |
| `backend/.env.example` | 文档化新增字段 `CLOUD_STORAGE_AES_KEY_DERIVE_FROM=SECRET_KEY`（说明性）|
| 前端 | 复用现有 `frontend-admin-pro` 依赖，无需新增 npm 包 |

---

## 四、迁移策略（历史数据怎么办）

### 4.1 现状盘点

- `cenkormes` 当前 `STORAGE_DRIVER=local`、`STORAGE_LOCAL_ROOT=./data/storage`
- 历史附件全部位于服务器本地磁盘

### 4.2 迁移路径

| 阶段 | 动作 | 风险 |
|---|---|---|
| 阶段 1 | 上线 cloud_storage 模块（默认仍为 local） | 无影响，老附件继续走本地 |
| 阶段 2 | 在后台配置目标云凭据 + 切换激活 provider | **新上传走云，老附件仍走本地** |
| 阶段 3 | 启动迁移任务 `POST /admin/cloud-storage/migrate`，把本地历史附件搬到云端 | 迁移期间本地与云端**双写** |
| 阶段 4 | 迁移完成后，**回填 attachment.storage_driver 字段**，前端展示时按字段选 driver 读 | 兼容期结束后可下线本地存储 |

### 4.3 兼容期设计

`Attachment` 表已有 `storage_driver` / `storage_key` 字段（`crud/attachment.py:34` 已写入）。前端读附件时：

```python
def attachment_url(att):
    if att.storage_driver == "local":
        return f"/api/files/{att.id}"
    else:
        return f"{CLOUD_BASE}/{att.storage_key}"  # 走云端签名URL
```

迁移期**两边都能读**，过渡期 1-3 个月后清理本地冗余。

---

## 五、风险与缓解

| 风险 | 影响 | 缓解措施 |
|---|---|---|
| `aiobotocore` 依赖体积大 | 镜像 +30MB，启动慢 0.5-1s | 可选 `extras_require` 分组，需要时再装 |
| SECRET_KEY 变更导致凭据失效 | 历史凭据全解密失败 | 文档明确告知，部署后**禁止改 SECRET_KEY**；提供凭据重新录入 UI |
| 阿里 OSS endpoint 配置错误 | 上传 4xx，定位耗时 | health_check 校验连通性，前端显示可读性错误 |
| 迁移任务中断 | 部分文件已迁移、部分未迁移 | 任务支持断点续传，按 key 跳过已迁移的 |
| MySQL vs PostgreSQL 差异 | DateTime / Boolean / Text 兼容 | 用 SQLAlchemy 通用类型，已实测 |
| 前端 Vue 3.5 vs 3.4 兼容 | element-plus 与 vue 3.5 警告 | 锁定 vue 3.4 不动 |

---

## 六、工时与分工

### 工时估算（单人开发）

| 模块 | 估时 |
|---|---|
| 后端搬运（7 个 driver + models + router + crypto）| 1-1.5 天 |
| alembic 迁移脚本编写 + 本地验证 | 0.5 天 |
| 路由 + 权限 + 启动注册 | 0.5 天 |
| 前端 Vue 页面搬运 + 菜单 + i18n | 0.5 天 |
| 联调测试 + 迁移功能验证 | 0.5 天 |
| 文档（README、运维手册） | 0.5 天 |
| **合计** | **3.5-4 天** |

### 建议分工（如多人）

- 后端 A：driver + factory 适配
- 后端 B：router + 迁移任务
- 前端：Vue 页面 + 菜单
- DBA：alembic 迁移脚本评审

---

## 七、待定项 / 需用户确认

1. **是否新增 `creds_local` / `creds_minio` 两列？**（cenkor-admin 没有，cenkormes 本地也是 driver 之一，建议加）
2. **是否保留独立的 `frontend-admin-pro` 路由**，还是像 cenkor-admin 那样做独立 Vite 应用？
3. **是否启用 `keep_local_backup` 默认值 `True`？**（建议默认 False，避免双写浪费）
4. **迁移任务是否纳入 P0？**（建议纳入 P1，因为大多数客户是「新建项目」，无历史附件）
5. **是否新增 `setup wizard`（首次部署引导填云存储）？**（建议有，提升交付体验）

---

## 八、开发任务清单（执行用）

### Phase 1：后端搬运（1.5 天）

- [ ] T1.1 新建 `backend/app/cloud_storage/__init__.py`，导出 router
- [ ] T1.2 搬运 `models.py`，改 `Base` 引用
- [ ] T1.3 搬运 `crypto.py`，改 `settings` 引用
- [ ] T1.4 搬运 7 个 driver 文件，无逻辑改动
- [ ] T1.5 搬运 `router.py`，**改 async 为 sync**（cenkormes 大部分 router 是 sync 风格），依赖注入改 `Depends(get_db)` 而不是 `AsyncSession`
- [ ] T1.6 `backend/app/api/router.py` 加 include_router
- [ ] T1.7 `backend/app/core/startup.py` 加 ensure_permissions

### Phase 2：数据库（0.5 天）

- [ ] T2.1 编写 `backend/alembic/versions/0005_cloud_storage.py`
- [ ] T2.2 本地 `alembic upgrade head` 验证
- [ ] T2.3 本地 `alembic downgrade base` 验证
- [ ] T2.4 提交迁移脚本

### Phase 3：前端（0.5 天）

- [ ] T3.1 搬运 `CloudStorageView.vue` → `frontend-admin-pro/src/pages/system/CloudStoragePage.vue`
- [ ] T3.2 适配 Element Plus 组件（Element Form / Input / Button 替换原 UI 框架）
- [ ] T3.3 加 `frontend-admin-pro/src/router/modules/system.ts` 路由
- [ ] T3.4 加 i18n（zh-CN + en-US）
- [ ] T3.5 `npm run build` 验证编译通过

### Phase 4：联调（0.5 天）

- [ ] T4.1 启动后端，验证 `/api/admin/cloud-storage/config` 返回 200
- [ ] T4.2 后台菜单能看到「云存储」入口
- [ ] T4.3 切到 local driver，上传一张，DB `storage_driver='local'`
- [ ] T4.4 切到 aliyun driver（测试环境填假凭据），health 应返回连通性失败但不报错
- [ ] T4.5 前端构建产物可在生产部署

### Phase 5：迁移功能（P1，0.5 天）

- [ ] T5.1 `_run_migration` 后台任务适配 cenkormes 调度器（不是 FastAPI BackgroundTasks）
- [ ] T5.2 进度字段实时更新（每秒刷新一次）
- [ ] T5.3 失败重试机制

### Phase 6：文档（0.5 天）

- [ ] T6.1 `README.md` 加云存储章节
- [ ] T6.2 `docs/pending/cloud_storage_plan.md`（本文档）实施完成后归档到 `docs/`
- [ ] T6.3 运维手册：4 种云的 endpoint 配置示例

---

## 九、参考资源

- 源项目路径：`/www/wwwroot/cenkor-admin/backend/src/cenkor_admin/apps/cloud_storage/`
- 源前端路径：`/www/wwwroot/cenkor-admin/backend/src/cenkor_admin/apps/cloud_storage/frontend/src/CloudStorageView.vue`
- 阿里 OSS S3 endpoint 格式：`https://oss-cn-hangzhou.aliyuncs.com`
- 腾讯 COS S3 endpoint 格式：`https://cos.ap-guangzhou.myqcloud.com`
- 七牛 Kodo S3 endpoint 格式：`https://s3-cn-east-1.qiniucs.com`
- aiobotocore 文档：https://aiobotocore.aiohl.readthedocs.io/

---

## 十、版本与变更

| 日期 | 版本 | 变更 | 作者 |
|---|---|---|---|
| 2026-08-03 | v0.1 草案 | 初稿，待启动 | AI 助理 |