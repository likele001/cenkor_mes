# CenkorMES 部署指南

覆盖两种主流部署方式：

1. **Docker Compose 一键部署** —— 后端 + MySQL 8 + Redis，适合快速上线 / 隔离环境。
2. **手动部署（本地 / 宝塔面板）** —— 适合已有 MySQL 环境、需要对前端做更多定制的场景。

> 规范端口：后端 **8000**（`config` 默认值、`vite` 开发代理、README、docker-compose 全部一致）。
> 若通过反向代理对外提供服务，代理请指向后端 8000。

---

## 0. 端口与账号速查

| 项 | 默认值 |
|----|--------|
| 后端 API | `http://localhost:8000/api`（交互文档 `/docs`） |
| 管理后台（dev） | `http://localhost:5174` |
| H5 移动端（dev） | `http://localhost:5173` |
| 默认管理员 | `admin` / `admin123`（首启自动创建，请立即修改） |
| 演示数据账号 | `123456`（执行 `seed_demo.py` 后可用） |

---

## 1. Docker Compose 一键部署

### 1.1 启动后端（含 MySQL 8 + Redis）

```bash
# 在仓库根目录
docker compose up -d --build
```

- 首次启动会自动建表（`DB_AUTO_CREATE=true`）并创建默认管理员（`DB_AUTO_SEED=true`）。
- 对外端口默认 8000，可用环境变量覆盖：`APP_PORT=9000 docker compose up -d --build`。
- **生产务必设置强 JWT 密钥**：`JWT_SECRET=xxxxxxxx docker compose up -d --build`。

验证：

```bash
curl http://localhost:8000/docs          # Swagger 交互文档
curl http://localhost:8000/api/health     # 健康检查（视实际路由）
docker compose ps
```

### 1.2 注入完整演示数据（可选，幂等可重复执行）

```bash
bash docker/scripts/init-demo.sh
```

### 1.3 前端如何运行

Docker 镜像当前只包含后端。前端（管理后台 / H5 / 小程序）推荐两种方式：

- **开发**：按第 2 节 `npm run dev`，让 vite 代理 `/api` 到 `127.0.0.1:8000`。
- **生产**：在宿主机 `npm run build` 后用 Nginx / 宝塔托管 `dist` 静态目录，
  并将 `/api/` 反向代理到后端 8000（示例见第 4 节）。

### 1.4 常用 Docker 命令

```bash
docker compose logs -f backend      # 查看后端日志
docker compose ps                   # 查看状态
docker compose down                 # 停止（保留数据卷）
docker compose down -v              # 停止并清空数据卷（谨慎）
```

---

## 2. 手动部署

### 2.1 准备 MySQL 与 Redis（可选）

```sql
CREATE DATABASE cenkormes DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

### 2.2 后端

```bash
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp env.example .env                 # 编辑 .env：DB_URL / JWT_SECRET 等
```

启动：

```bash
# 开发（自动热重载）
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# 生产（建议由 Nginx 反向代理）
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

首次启动自动建表 + 创建默认管理员。注入演示数据（可选）：

```bash
python scripts/seed_demo.py         # 幂等，可重复执行
```

### 2.3 前端（管理后台 / H5）

```bash
cd frontend-admin-pro
npm install
npm run dev -- --port 5174          # 开发
npm run build                       # 生产：产物在 dist/
```

```bash
cd frontend-h5
npm install
npm run dev -- --port 5173          # 开发
```

> 注意：vite 开发代理将 `/api` 转发到 `http://127.0.0.1:8000`
> （见 `frontend-admin-pro/vite.config.ts`）。后端端口需保持一致。

---

## 3. 一条开发命令（本地）

```bash
./start.sh          # dev：后端 :8000 + 管理后台 :5174 + H5 :5173
./start.sh --prod   # prod：后端无 reload，前端 build 后 preview 托管
```

---

## 4. Nginx 反向代理示例（生产）

```nginx
server {
    listen 80;
    server_name mes.example.com;

    client_max_body_size 20m;

    # 管理后台静态资源
    location / {
        root /www/wwwroot/cenkormes/frontend-admin-pro/dist;
        try_files $uri $uri/ /index.html;
    }

    # H5 端
    location /h5/ {
        alias /www/wwwroot/cenkormes/frontend-h5/dist/;
        try_files $uri $uri/ /h5/index.html;
    }

    # 后端 API
    location /api/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

> 部署在反向代理 / HTTPS 后时，请在 `backend/.env` 中把 `PUBLIC_BASE_URL`
> 与 `H5_PUBLIC_BASE_URL` 配置为对外可访问的 HTTPS 地址，保证生成的
> 打印、分享、回调链接正确。

---

## 5. 环境变量说明

| 变量 | 默认 | 说明 |
|------|------|------|
| `APP_ENV` | `dev` | `dev` 下 uvicorn 自动 `--reload` |
| `APP_PORT` | `8000` | 后端监听端口 |
| `DB_URL` | `mysql+pymysql://...cenkormes...` | 数据库连接串，库名默认 `cenkormes` |
| `DB_AUTO_CREATE` | `true` | 首启自动按 ORM 建表 |
| `DB_AUTO_SEED` | `true` | 首启自动创建默认管理员 |
| `JWT_SECRET` | 无默认强值 | **生产必须自设强随机串** |
| `PUBLIC_BASE_URL` | — | 对外访问地址（打印/分享/回调） |
| `STORAGE_DRIVER` | `local` | 存储驱动：local / aliyun_oss / tencent_cos / qiniu |
| `REDIS_URL` / `CELERY_*` | — | Redis 与 Celery 任务队列 |

---

## 6. 安全基线（上线前）

- 立即修改默认管理员 `admin` 密码，并关闭弱口令。
- 设置强随机 `JWT_SECRET`。
- 生产将 `APP_ENV` 置为 `prod`，关闭 `--reload`。
- 为 MySQL、Redis 设置强账号密码（默认仅用于本地演示）。
- 通过 HTTPS + Nginx 对外提供，`PUBLIC_BASE_URL` 指向 HTTPS 地址。

更多详见 [`SECURITY.md`](../SECURITY.md)。