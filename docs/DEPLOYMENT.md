# CenkorMES 部署指南

覆盖两种主流部署方式：

1. **Docker Compose 一键部署（全栈）** —— 一条命令拉起后端 + MySQL 8 + Redis + 管理后台 + 员工 H5，快速上线 / 隔离环境。
2. **手动部署（本地 / 宝塔面板）** —— 适合已有 MySQL 环境、需要对前端做更多定制的场景。

> 默认端口（均可用仓库根 `.env` 覆盖）：后端 API **8000**、管理后台 **8080**、员工 H5 **8081**。
> 前端容器内已内置 nginx，`/api` 自动反代到后端，拿到即可访问、无需再配前端。

---

## 0. 端口与账号速查

| 项 | 默认值 |
|----|--------|
| 后端 API | `http://localhost:8000/api`（交互文档 `/docs`） |
| 管理后台（生产/Docker） | `http://localhost:8080` |
| 员工 H5（生产/Docker） | `http://localhost:8081` |
| 管理后台（dev） | `http://localhost:5174` |
| H5 移动端（dev） | `http://localhost:5173` |
| 默认管理员 | `admin` / `admin123`（首启自动创建，请立即修改） |
| 演示数据账号 | `123456`（执行 `seed_demo.py` 后可用） |

---

## 1. Docker Compose 一键部署

### 1.1 启动完整系统（后端 + MySQL 8 + Redis + 管理后台 + H5）

```bash
# 在仓库根目录
docker compose up -d --build
```

- 首次启动会自动建表（`DB_AUTO_CREATE=true`）并创建默认管理员（`DB_AUTO_SEED=true`）。
- 管理后台与 H5 由前端容器内的 nginx 托管，`/api` 自动反代到后端，开箱即用。
- 对外端口可用环境变量覆盖：
  `APP_PORT=9000 WEB_ADMIN_PORT=9001 WEB_H5_PORT=9002 docker compose up -d --build`。
- **JWT 密钥**：未设置时容器入口自动生成临时随机密钥保证一键可启动；生产部署请设置固定强密钥
  ```bash
  JWT_SECRET=REPLACE_ME_8uP3aXq9vN2kLmR7sT5cHd2jF0bWz6eY4gQ1oI9nBxC3 # ≥32 位，务必替换为你自己的（生成: python3 -c "import secrets;print(secrets.token_urlsafe(48))"）
  docker compose up -d --build
  ```
  （临时密钥重启容器后失效，会导致已登录用户需重新登录）

验证：

```bash
curl http://localhost:8000/docs            # Swagger 交互文档
curl http://localhost:8080                 # 管理后台
curl http://localhost:8081                 # 员工 H5
curl http://localhost:8000/api/health      # 健康检查（视实际路由）
docker compose ps
```

### 1.2 注入完整演示数据（可选，幂等可重复执行）

```bash
bash docker/scripts/init-demo.sh
```

### 1.3 前端如何运行

Docker 镜像已把管理后台与员工 H5 **一起容器化**：

- **生产（Docker）**：`docker compose up -d --build` 会一并构建并托管管理后台（`:8080`）与 H5（`:8081`），前端 nginx 把 `/api` 反代到后端，开箱即用。
- **开发**：按第 2 节 `npm run dev`，让 vite 代理 `/api` 到 `127.0.0.1:8000`。
- **宿主机生产**：`npm run build` 后用 Nginx / 宝塔托管 `dist` 静态目录，并将 `/api/` 反向代理到后端 8000（示例见第 4 节）。

### 1.4 常用 Docker 命令

```bash
docker compose logs -f backend      # 查看后端日志
docker compose ps                   # 查看状态
docker compose down                 # 停止（保留数据卷）
docker compose down -v              # 停止并清空数据卷（谨慎）
```

### 1.5 离线安装包（内网 / 无外网部署）

在能联网且已成功 `docker compose build` 的机器上生成一次离线包：

```bash
bash docker/scripts/export-images.sh             # 导出全部镜像（含 MySQL/Redis）到 dist-images/
```

目标机（无外网）导入并启动：

```bash
docker load < dist-images/cenkormes_images_*.tar.gz
docker compose up -d                             # 无需再联网拉取 / 构建
```

> 离线包内含 `cenkormes-backend` / `cenkormes-web-admin` / `cenkormes-web-h5` 及
> `mysql:8.0` / `redis:7-alpine`，覆盖全栈所需镜像。

### 1.6 多架构构建（linux/amd64 + linux/arm64）

默认构建跟随当前主机架构。需要同时产出 x86_64 与 ARM64 镜像时（如发布到镜像仓库 / 同时交付两种服务器）：

```bash
# 1) 启用 BuildKit 多架构（ARM64 交叉需 binfmt，首次执行一次即可）
docker buildx create --name multi --use
docker run --privileged --rm tonistiigi/binfmt --install all

# 2) 后端（架构无关，同一份镜像）
docker buildx build --platform linux/amd64,linux/arm64 \
  -f backend/Dockerfile -t cenkormes-backend:multi --load .

# 3) 前端（管理后台 / H5）
docker buildx build --platform linux/amd64,linux/arm64 \
  -f docker/frontend/Dockerfile --build-arg FRONTEND=frontend-admin-pro -t cenkormes-web-admin:multi --load .
docker buildx build --platform linux/amd64,linux/arm64 \
  -f docker/frontend/Dockerfile --build-arg FRONTEND=frontend-h5 -t cenkormes-web-h5:multi --load .
```

> 说明：多架构构建磁盘与网络开销较大；多个平台镜像通过单一 tag 分发（media-type OCI manifest
> list），运行时按目标机架构自动拉取对应构建。发布到 registry 时改用 `--push`（去掉 `--load`）。
> 后端镜像已精简（去掉 gcc/mysqlclient 编译链，仅保留 PyMySQL 与运行时系统库 libgomp1）。

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

> vite 开发代理默认将 `/api` 转发到 `http://127.0.0.1:8000`，可通过环境变量 `VITE_API_PROXY`
> 指定其它后端地址（例如 `VITE_API_PROXY=http://127.0.0.1:8500 npm run dev`），
> 避免本机 8000 被其它项目占用时 `/api` 串到错误服务。
> 生产构建不受影响：产物由 Nginx / 宝塔反代到真实后端端口。

---

## 3. 一条开发命令（本地）

```bash
./start.sh          # dev：后端 :8000 + 管理后台 :5174 + H5 :5173
./start.sh --prod   # prod：后端无 reload，前端 build 后 preview 托管

# 后端端口被占用时可改端口，前端 /api 代理会自动跟随：
BACKEND_PORT=8500 ./start.sh
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

### 4.1 Docker 全栈部署的域名绑定与 HTTPS 配置

Docker 全栈部署下，前端容器内的 nginx 已自带「静态托管 + `/api` 反代」，无需再配置
后端 API 反代。但当需要对外用 **域名 + HTTPS** 访问时，需在宿主机加一层「入口代理」，
把域名转发到容器对外映射的端口（管理后台 `8080` / 员工 H5 `8081`）。

默认情况下后端**不校验 Host 头**（`TRUSTED_HOSTS` 留空即不启用校验），因此绑定任意
域名即可直接访问。若在 `.env` 配置了 `TRUSTED_HOSTS`（逗号分隔白名单），必须把对外
域名加入，否则会被 403 拦截：

```bash
# backend/.env（或在仓库根 .env 通过 compose 注入）
TRUSTED_HOSTS=admin.example.com,h5.example.com
```

#### 方式 A：宝塔面板（推荐，可视化）

1. **解析域名**：在域名 DNS 添加 A 记录指向服务器 IP。管理后台与 H5 是独立端口，建议用
   两个子域名，避免同一域名按路径分流导致 SPA 路由错乱：
   - `admin.example.com  →  111.222.33.44`（管理后台）
   - `h5.example.com     →  111.222.33.44`（员工 H5）
2. **添加站点**：宝塔「网站 → 添加站点」，分别绑定上述两个域名（纯静态站点，无需上传文件）。
3. **配置反向代理**：以管理后台为例，网站设置 → 反向代理 → 添加，目标填
   `http://127.0.0.1:8080`；H5 站点目标填 `http://127.0.0.1:8081`。
4. **SSL 证书**：站点设置 → SSL → Let's Encrypt 申请证书，并开启「强制 HTTPS」。
   如需把 HTTPS 正确回报给后端，在反代配置补充：
   ```nginx
   proxy_set_header X-Forwarded-Proto https;
   proxy_set_header X-Forwarded-Host  $host;
   ```

#### 方式 B：系统 Nginx + certbot

为管理后台创建 `/etc/nginx/conf.d/admin.example.com.conf`：

```nginx
server {
    listen 80;
    server_name admin.example.com;
    location / {
        proxy_pass http://127.0.0.1:8080;
        proxy_set_header Host              $host;
        proxy_set_header X-Real-IP         $remote_addr;
        proxy_set_header X-Forwarded-For   $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto https;
    }
}
```

H5 同理（`server_name h5.example.com`，`proxy_pass http://127.0.0.1:8081`），再执行
`certbot --nginx -d admin.example.com -d h5.example.com` 自动签发并续期证书。

#### 需要留意的点

- 后端默认不校验 Host，直接可用；配置了 `TRUSTED_HOSTS` 后必须把域名加进白名单。
- 容器内 nginx 是内部 http 访问后端，入口层传 `X-Forwarded-Proto https` 可让后端生成
  HTTPS 链接；纯 API 调用不受影响。
- 如需打印 / 分享 / 回调链接为 HTTPS，同时把 `PUBLIC_BASE_URL` 与 `H5_PUBLIC_BASE_URL`
  指向对外 HTTPS 地址。

---

## 5. 环境变量说明

| 变量 | 默认 | 说明 |
|------|------|------|
| `APP_ENV` | `dev` | `dev` 下 uvicorn 自动 `--reload` |
| `APP_PORT` | `8000` | 后端监听端口 |
| `DB_URL` | `mysql+pymysql://...cenkormes...` | 数据库连接串，库名默认 `cenkormes` |
| `DB_AUTO_CREATE` | `true` | 首启自动按 ORM 建表 |
| `DB_AUTO_SEED` | `true` | 首启自动创建默认管理员 |
| `JWT_SECRET` | 无默认强值 | **生产必须自设强随机串**；`APP_ENV=prod` 时若为默认/过短将拒绝启动 |
| `CORS_ORIGINS` | 空 | 逗号分隔白名单；留空不开 CORS（推荐 Nginx 同域反代） |
| `TRUSTED_HOSTS` | 空 | 逗号分隔 Host 白名单；留空不校验，生产建议固定 |
| `PASSWORD_MIN_LENGTH` | `6` | 用户密码最小长度 |
| `PUBLIC_BASE_URL` | — | 对外访问地址（打印/分享/回调） |
| `STORAGE_DRIVER` | `local` | 存储驱动：local / aliyun_oss / tencent_cos / qiniu |
| `REDIS_URL` / `CELERY_*` | — | Redis 与 Celery 任务队列 |

---

## 6. 安全基线（上线前）

内置加固（无需配置即生效，全部响应携带安全头）：

- 安全响应头：`X-Content-Type-Options: nosniff`、`X-Frame-Options: DENY`、
  `Referrer-Policy`、`X-XSS-Protection`、`Permissions-Policy`（不覆盖反向代理已设的值）。
- 密码强度：`create_user` / `set_password`（改密、重置、建号）统一校验
  `PASSWORD_MIN_LENGTH` 与字符多样性，弱口令返回友好 400 提示。
- 对称环境差异：`APP_ENV=prod` 时若 `JWT_SECRET` 仍为默认/不足 32 位，启动直接
  fail-fast 拒绝运行，杜绝用已知弱密钥伪造令牌。

上线 Checklist：

- 立即修改默认管理员 `admin` 密码，并关闭弱口令。
- 设置强随机 `JWT_SECRET`（≥32 位）：`python3 -c "import secrets;print(secrets.token_urlsafe(48))"`。
- 设置 `APP_ENV=prod` 关闭 `--reload`；在 `backend/.env` 配置 `TRUSTED_HOSTS`。
- 多端直连后端（非 Nginx 反代）时，按需配置 `CORS_ORIGINS` 白名单。
- 为 MySQL、Redis 设置强账号密码（默认仅用于本地演示）。
- 通过 HTTPS + Nginx 对外提供，`PUBLIC_BASE_URL` 指向 HTTPS 地址。

更多详见 [`SECURITY.md`](../SECURITY.md)。

---

## 7. 数据备份与恢复

CenkorMES 业务数据存于 MySQL，文件存于本地卷（`STORAGE_LOCAL_ROOT`）或对象存储。
**生产上线前务必配置周期性备份。**

### Docker 部署（MySQL 在容器中）

```bash
# 逻辑备份到宿主机（utf8mb4 中文友好）
docker compose exec -T mysql mysqldump \
  -uroot -proot --default-character-set=utf8mb4 --single-transaction \
  cenkormes > backup/cenkormes_$(date +%F_%H%M).sql

# 恢复（先确认目标库为空或可覆盖）
docker compose exec -T mysql mysql -uroot -proot cenkormes < backup/cenkormes_xxxx.sql

# 文件卷备份（Docker 命名卷）
docker run --rm -v cenkormes_storage_data:/data -v "$PWD/backup":/backup \
  busybox tar czf /backup/storage_$(date +%F).tar.gz -C /data .
```

> 备份卷名以 `docker compose volume ls` 实际输出为准；`root` 密码默认 `root`，
> 生产务必改为强密码并在命令中替换。

### 手动 / 宝塔部署

- 宝塔面板「数据库」可对 `cenkormes` 库一键备份/定时任务；存储目录
  `backend/data/storage` 单独打包。
- 裸机 crontab 示例（每天 02:30 备份 + 保留 14 天）：

```bash
30 2 * * *  mysqldump --default-character-set=utf8mb4 --single-transaction -uroot -p'密码' cenkormes | gzip > /data/backup/cenkormes_$(date +\%F).sql.gz && find /data/backup -name '*.sql.gz' -mtime +14 -delete
```

### 恢复要点

- 恢复前备份当前库；导入新 dump 前最好清空目标库避免主键冲突。
- 先验证 dump 中账号数据完整（`users` / `roles` / `orders` 等表），再切换流量。
- 对象存储（阿里云 OSS 等）建议同时开启服务商侧回收站 / 跨区冗余。
