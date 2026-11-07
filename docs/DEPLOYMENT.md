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

### 1.5 离线部署包（内网 / 无外网部署）

在已成功 `docker compose build` 的构建机上制作**自包含**离线包：

```bash
bash scripts/make-offline-bundle.sh              # 输出到 ./dist-offline
bash scripts/make-offline-bundle.sh /data/pkg    # 或指定输出目录
```

产物 `cenkormes-offline-vX.Y.Z-<时间戳>.tar.gz` 内含镜像、compose 文件、`.env` 模板、
`VERSION` 与 `MANIFEST.txt`、安装脚本和自检脚本，客户机不用再自己凑文件：

```bash
sha256sum -c cenkormes-offline-vX.Y.Z-*.tar.gz.sha256   # 先校验传输完整性
tar xzf cenkormes-offline-vX.Y.Z-*.tar.gz
cd cenkormes-offline-vX.Y.Z-*
bash install.sh                                          # 一条命令装完
```

`install.sh` 依次完成：检查 Docker → 导入镜像 → 生成 `.env`（**自动填 48 字节随机
JWT_SECRET**，避免装完就是弱口令）→ `compose up -d` → 轮询健康 → 跑部署自检。
宿主机 8000 被占用时用 `APP_PORT=18000 bash install.sh` 换端口。

> 只要镜像、不需要安装流程时，仍可单独用 `bash docker/scripts/export-images.sh`。
> 但它只导出镜像 tar，配套文件得自己准备——现场很容易漏 `.env` 或用错版本 compose，不推荐。

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

> 生产**不要**就这样裸跑：进程退出后没人拉起，在线升级也没有可依赖的自愈机制。
> 用 §2.5 的 systemd 单元托管。

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

### 2.4 Celery Worker / Beat（异步任务与定时任务）

薪资计算、自动化流水线、扩展包定时任务等依赖 Celery。Worker 消费队列，Beat 用
`DatabaseScheduler` 从 `cron_jobs` 表读取调度；两者都不是 uvicorn 进程的一部分，需单独常驻。

裸机 / 宝塔可直接使用仓库模板（先按实际路径修改 `WorkingDirectory`、`ExecStart`、`User`）：

```bash
cp scripts/systemd/cenkormes-celery.service /etc/systemd/system/
cp scripts/systemd/cenkormes-beat.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now cenkormes-celery cenkormes-beat
```

> Worker 重启走 Celery 控制通道，Beat 重启走 Redis 退出信号（beat 自行退出、
> systemd `Restart=always` 拉起），**全程不需要 root / sudo / polkit**——
> 后端以 `www` 用户运行即可。
>
> Worker 的 `-n` 主机名必须以 `CELERY_WORKER_PREFIX`（默认 `cenkormes_worker@`）开头，
> Beat 单元名必须与 `BEAT_SERVICE_NAME`（默认 `cenkormes-beat`）一致，否则管理后台
> 「系统 → 定时任务」页无法定向查看/重启。一个 broker 上跑多个项目时，务必保留前缀，
> 避免重启广播误伤其它项目的 Worker。

管理后台的「定时任务」页提供 Worker / Beat 状态卡：

- Worker 重启 = 广播 `shutdown`，处理完在飞任务后退出，由 systemd（`Restart=always`）拉起新代码；
- Beat 重启 = 向 Redis（`REDIS_URL`）写 `celery:beat:shutdown` 退出信号，beat 的
  `DatabaseScheduler` 每 10 秒检查一次，收到后退出并由 systemd 拉起新进程；
  Beat 未运行时拒绝重启（需在服务器上手动启动）；
- 后端轮询上限 45 秒（低于 nginx `proxy_read_timeout` 60s），失败会返回明确错误
  而不是被 nginx 掐成 504；等待超时时会清掉残留退出信号，防止之后拉起的新 Beat
  立刻再退一次；
- **一次性引导**：升级到带退出信号检查的调度器后，正在运行的旧 Beat 不认识
  `celery:beat:shutdown`，页面上点「重启 Beat」会报「未检测到新进程」。此时先手动
  重启一次（`systemctl restart cenkormes-beat`），之后按钮长期可用；
- 页面需要 `setting.manage` 权限；SaaS 模式下重启属平台运维，租户端只读；
- Docker 部署若没有 systemd 单元，Beat 卡会显示「未安装」，请把两个进程作为独立服务/容器常驻。

---

### 2.5 用 systemd 托管后端（生产推荐）

仓库自带主服务单元 `scripts/systemd/cenkormes.service`，与已有的
`cenkormes-celery.service` / `cenkormes-beat.service` 口径一致：

```bash
cp scripts/systemd/cenkormes.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now cenkormes
systemctl status cenkormes
```

安装前按现场改三处：`WorkingDirectory`、`ExecStart`、`User`；`ExecStart` 里的
`--port` 必须与 `backend/.env` 的 `APP_PORT` 一致。

> **不要给这个单元加 `PrivateTmp=true` 或 `ProtectSystem=strict`。**
> 在线升级把重启结论写在 `/tmp/cenkormes-upgrade-restart-{job}.json`，服务重启后
> 由新进程读回这份文件来判定升级结果。`PrivateTmp` 会给每次启动一个私有 `/tmp`，
> 重启后**读不到上一轮写的结果文件**，升级任务会一直挂在 `running` 直到超时。
> 这属于「看起来更安全、实际把功能搞坏」的典型配置。

`Restart=always` + `RestartSec=5` 就是自愈：升级链路 kill 掉旧进程后，systemd 在
5 秒内拉起新进程，不需要任何人工干预。

### 2.6 部署后自检

任何部署方式（Docker / 裸装 / 宝塔）完成后都跑一次：

```bash
bash scripts/post-deploy-check.sh
```

五项检查：服务健康与版本一致性、数据库迁移是否到 head、上传目录可写、
celery/beat 是否运行、关键配置（`.env` / `JWT_SECRET` / `APP_ENV`）。

输出分 `PASS` / `WARN` / `SKIP` / `FAIL`，**只有 FAIL 让退出码变 1**。容器里没有
systemctl 时 celery 检查自动 SKIP，不用手工加参数。

解读要点：

- `WARN` 不阻塞部署，但上线前应逐条确认。典型场景是 `APP_ENV=dev`（后端不会校验
  JWT 密钥强度，异常详情也可能回显给前端）或密钥长度不足 32 位（改 prod 后会直接
  拒绝启动）。
- `FAIL 版本不一致` 几乎一定是后端没重启，新代码还没加载。
- `FAIL 迁移未到 head` 说明该跑 `alembic upgrade head` 了。

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
| `CELERY_WORKER_PREFIX` | `cenkormes_worker@` | 管理后台托管的 Worker 主机名前缀；留空关闭 Worker 管理（防误伤其它项目） |
| `CELERY_WORKER_SERVICE` | `cenkormes-celery` | Worker 的 systemd 单元名，仅用于页面离线提示 |
| `BEAT_SERVICE_NAME` | `cenkormes-beat` | Beat 的 systemd 单元名；留空关闭 Beat 管理 |

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

---

## 8. 升级（自托管用户）

> 版本号真源为根目录 `VERSION`；「关于/版本」页显示当前实例所跑版本，
> 对照 [CHANGELOG](../backend/CHANGELOG.json) 决定是否升级。

> 发版侧（维护者怎么打 tag、CI 怎么出包）见 [RELEASE_PROCESS.md](./RELEASE_PROCESS.md)。

升级通道只有一条：**下载发布产物包**。包里已经带好预构建的前端 `dist`，
所以升级既不需要 `git`、也不需要 SSH key、更不需要在服务器上装 node。

### 8.1 获取新版本

每个 `vX.Y.Z` 的 GitHub Release 提供两个附件：

| 附件 | 用途 |
|---|---|
| `cenkormes-vX.Y.Z.tar.gz` | 完整产物包（代码 + 预构建 dist），约 8 MB |
| `cenkormes-vX.Y.Z.tar.gz.sha256` | 摘要，安装前必须校验 |

Source code (tar.gz/zip) 是 GitHub 自动生成的**源码**快照，**不含前端产物**，
不能直接拿来部署（除非你打算自己在服务器上 `npm ci && npm run build`）。

### 8.2 一键升级脚本（裸机 / 宝塔）

```bash
bash scripts/upgrade.sh --list                 # 列出远端可安装的版本
bash scripts/upgrade.sh                        # 装最新正式版
bash scripts/upgrade.sh --version v2.2.1       # 装指定版本（也可用于修复被改坏的文件）
bash scripts/upgrade.sh --dry-run              # 只打印将执行的动作
bash scripts/upgrade.sh --skip-backup          # 跳过数据库备份（不推荐）
bash scripts/upgrade.sh --git                  # 开发机：改回 git fetch/checkout
```

脚本做的事：备份数据库 → 下载产物包 → **校验 SHA256** → 解包 → 覆盖代码
→ `pip install -r requirements.txt` → `alembic upgrade head` → 提示重启。

覆盖安装**只写包内存在的文件**，并且**永不覆盖**这些现场资产：

- `backend/.env`（以及任何 `.env*`）
- `backend/data/`（上传件、备份、扩展、模型、日志）
- `node_modules/`、`.git/`

> 脚本**不会重启任何服务**。跑完后需**手动重启后端**（uvicorn / celery）才生效。
> 重启完跑一次 `bash scripts/post-deploy-check.sh` 确认闭环：版本是否真的换了、
> 迁移是否到 head、celery 有没有跟着重启，一次全告诉你。

### 8.3 手动升级步骤（务必按此顺序）

```bash
# ① 备份数据库（见第 7 节）+ 备份 backend/.env
# ② 下载产物包并校验
TAG=v2.2.1
curl -fsSL -O https://github.com/likele001/cenkor_mes/releases/download/$TAG/cenkormes-$TAG.tar.gz
curl -fsSL -O https://github.com/likele001/cenkor_mes/releases/download/$TAG/cenkormes-$TAG.tar.gz.sha256
sha256sum -c cenkormes-$TAG.tar.gz.sha256 --ignore-missing
# ③ 只覆盖代码，不动现场资产
mkdir -p /tmp/pkg && tar xzf cenkormes-$TAG.tar.gz -C /tmp/pkg
tar -C /tmp/pkg/cenkormes-$TAG -c --exclude='./backend/data' --exclude='./backend/.env' --exclude='./.env' . \
  | tar -C /你的部署目录 -x
# ④ 更新依赖
cd backend && pip install -r requirements.txt
# ⑤ 先迁移数据库（此时 app 未运行，不会抢建表）
alembic upgrade head
# ⑥ 最后再启动新后端（加载新路由 + 同步版本页）
```

**不需要 `npm run build`**：包内已经是构建好的 `dist`。这一点和旧文档不同——
旧流程要求每台机器都装 node，内网环境经常卡在这里。

Docker 部署则：`docker compose pull`（或 `docker compose build`）→ 进 backend 容器
`alembic upgrade head` → `docker compose up -d`。

### 8.4 关键注意事项

- **先迁移、后启动**：生产 `DB_AUTO_CREATE` 建议保持 `false`（本仓库默认已改），schema 完全由 alembic 权威管理。若为 `true`，新后端启动时 `create_all` 会抢在新迁移前建表，导致 `alembic upgrade head` 报 `1050 Table already exists`。
- **全新安装**：首次部署需先跑 `alembic upgrade head` 建表（或临时置 `DB_AUTO_CREATE=true` 启动一次建表后再改回 `false`）。
- **迁移不可跳**：`alembic upgrade head` 会按序补齐所有中间版本迁移，无需逐版升级；升级前务必先备份。
- **回滚**：数据库用备份 dump 恢复；代码**重新安装上一个版本的产品包**
  （`bash scripts/upgrade.sh --version v2.2.0`），不需要本地留着 git 历史。
- **重启由运维执行**：本仓库约定服务启停由人工完成，升级脚本与文档均不自动重启。
- **不要手改包内文件**：现场改动会被下一次升级覆盖；需要长期生效的定制请走扩展机制。

### 8.5 后台「在线升级」按钮

「关于/版本」页的升级与回滚按钮走的是**同一套产物包**，只是由后端代跑：

| 环节 | 需要什么 | 说明 |
|---|---|---|
| 查最新版本 | 能访问 `api.github.com` | 公开仓库匿名读，不需要令牌 |
| 下载产物包 | 能访问 `github.com` | 走 Release 附件，直链下载 |
| 校验 | 无需额外依赖 | 优先用接口自带 digest，其次 `.sha256` 附件；两者都没有会**拒绝安装** |
| 前端 | **不需要 node** | 包内已带 dist，原子换入 |
| 数据库备份 | `mysqldump` | 失败即中止，绝不带病继续 |

相关环境变量：

| 变量 | 默认值 | 作用 |
|---|---|---|
| `CENKORMES_UPGRADE_MODE` | `artifact` | `artifact` 产物包；`git` 开发机用；`auto` 按有无 `.git` 自动选 |
| `CENKORMES_REPO` | `likele001/cenkor_mes` | 私有化部署指向自己的仓库 |
| `CENKORMES_GITHUB_API` | `https://api.github.com` | 内网镜像或 GitHub Enterprise |
| `CENKORMES_ALLOW_UNVERIFIED` | 空 | 设 `1` 才允许安装无摘要的包（不建议） |
| `CENKORMES_RESTART_CMD` | 空 | 自定义重启命令（整段接管重启）；不配则杀监听进程，再由下面的 `CENKORMES_START_CMD` 拉起 |
| `CENKORMES_START_CMD` | 空 | 杀掉旧进程后**主动拉起**后端的命令；不配则等服务管理器自己巡检（宝塔默认 120s） |
| `CENKORMES_CELERY_UNITS` | `cenkormes-celery cenkormes-beat` | 升级后要重启的 worker 单元名 |

> 若服务器完全无外网，请用 8.2/8.3 的离线方式：把包下载到内网后手动覆盖安装。
> 后台按钮在没有外网时只会提示「无法检查更新」。

#### 8.5.1 把升级停机从「两分钟」压到「十秒」（宝塔现网做法）

后台升级会 kill 掉 8500 上的 uvicorn，再由服务管理器把新进程拉起来。宝塔的
Python 项目管理器是**定时巡检**（默认 120s 一轮），所以不配任何东西时，停机
时间 ≈ 一个巡检周期；配好 `CENKORMES_START_CMD` 后由升级脚本在 kill 完立刻
调面板自己的启动入口，实测 **kill → 恢复 9 秒左右**。

三个动作都在服务器上做，只做一次（不进产物包，升级不会覆盖）：

```bash
# 1) 放一个 root 属主的启动封装：只允许启动白名单里的项目，其它参数一律拒绝
#    源码在 scripts/panel/btpy-project-start（不进产物包，由运维手工安装）
install -o root -g root -m 755 scripts/panel/btpy-project-start /usr/local/bin/btpy-project-start

# 2) 给 www 一条固定的 sudo 白名单，只授权「启动 cenkermes 项目」这一件事
echo 'www ALL=(root) NOPASSWD: /usr/local/bin/btpy-project-start cenkermes' \
  >> /etc/sudoers.d/cenkormes-services
visudo -c

# 3) 告诉升级脚本杀完用什么拉起（进程环境变量或 backend/.env 都认）
echo 'CENKORMES_START_CMD="sudo -n /usr/local/bin/btpy-project-start cenkermes"' \
  >> backend/.env
```

为什么必须走面板入口、而不是在应用里自己 `nohup uvicorn`：手起的进程会抢 8500
端口，面板自愈随后反复 `address already in use`；pidfile 也不归面板管，后台的
启动/停止/日志全部失准。封装内部调的是面板 `ServiceManager.start_project()`，
进程身份、日志、pidfile 都和手点「启动」完全一致，且被拉起的进程仍是 `www`，
升级流程拿不到额外权限。

没配这一步也能用，只是停机时间退回一个巡检周期：

**v2.2.20 修掉了一个会让停机变成 11 分钟的真 bug**：守护脚本是从 uvicorn 里
spawn 的，会原样继承启动脚本 `export` 的 `BT_PYTHON_SERVICE_SID`；而宝塔判断
「项目是否在跑」就是扫 `/proc/<pid>/environ` 找这个变量。于是脚本等健康的那
600 秒里，面板每一轮都认为服务还活着，一次都没拉起 uvicorn。现在启动守护脚本
前会把这个变量摘掉（`_guard_env()`），脚本一退出面板下一轮就能接手。

宝塔侧还有一个可调项：`/www/server/panel/data/daemon_time.pl`（单位秒，默认
120）。它是**整台机器**共用，改小会让面板巡检所有 Python 项目更频繁，一般
不建议动——用 `CENKORMES_START_CMD` 更精准。

## 9. 前端产物属主（在线升级前置条件）

后端服务与在线升级均以 `www` 用户运行，`frontend-*/dist` 必须属于 `www:www`。
若用 root 手动执行 `npm run build` 或 rsync 上传 dist，目录会变成 `root:root`：
在线升级换入产物时 `_promote_frontend()` 里的 `shutil.rmtree(dist.__bak, ignore_errors=True)`
删不掉旧产物且会静默忽略，残留持续占空间，还会让后续 rename 与回滚失败
（2026-11-02~11-05 任务 #7 反复出现 disk full 的诱因之一）。

手动构建或上传前端产物后，务必执行：

```bash
chown -R www:www frontend-admin-pro/dist frontend-h5/dist
```

CI 产物包由升级进程（www）解压，属主天然正确，无需额外处理。

### 9.1 覆盖前可写性预检与重启判定

v2.2.4 起，`_apply_package()` 在写第一个文件之前会对整批目标路径做可写性
预检（普通文件看写位，前端 `dist` / `dist.__bak` 目录树逐层看写+执行位），
不通过就抛 `PreflightError` 并**直接中止、不回灌**——避免在属主异常时留下
半新半旧的代码。报错信息会列出前 5 个问题路径并给出 `chown` 命令。

**重启判定现状（v2.2.20）**：守护脚本以独立会话 + `/tmp` 为 cwd 启动，
**自己轮询 `/api/health` 直到版本匹配**，结果文件只写终态 `ok=1` / `ok=0`，
绝不写 `pending` 这类需要上层二次解释的中间态（回滚后是旧代码在读这个文件，
旧代码只认终态）。

为什么不能「只 kill 就退出」（v2.2.5 曾这么改过）：面板把「脚本还活着」当成
「项目在跑」，脚本退出前它不会拉起 uvicorn——窗口从 180s 加到 420s，8500 反而
停了 7 分钟。真正的解法不是缩窗口，而是让脚本**不像**项目主进程：独立会话、
`cwd=/tmp`、并抹掉 `BT_PYTHON_SERVICE_SID`（v2.2.20，见 8.5.1；漏掉最后一项
时脚本活满 600s，面板就当项目一直在跑，实测停机 11 分钟）。

最终状态由服务被面板拉起后判定：

- `reconcile_jobs()` 实测 `/api/health`，版本精确等于 `to_version` 才判成功；
- startup 钩子早于端口可用时暂缓判定（10 分钟宽限，保留 `running/restart`）；
- `main.py` 启动后另起 daemon 线程，30/60/90s 各复核一次，自动定终态；
- 后台「健康校验」按钮可纠正误判的 `failed`（要求实测版本匹配 + 有守护结果文件）。

因此不需要也不应该配置任何「健康等待窗口」环境变量；
`CENKORMES_VERIFY_TIMEOUT` 已随 v2.2.5 移除。
