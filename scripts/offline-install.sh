#!/usr/bin/env bash
# CenkorMES 离线一键安装（目标机执行，无需外网）
#
# 前提：本目录内有 images/*.tar.gz、docker-compose.yml、VERSION。
# 需要目标机已装 Docker 与 compose 插件（离线环境请提前装好）。
#
# 用法：
#   tar xzf cenkormes-offline-vX.Y.Z-*.tar.gz
#   cd cenkormes-offline-vX.Y.Z-*
#   bash install.sh
#
# 常用可选参数（环境变量）：
#   APP_PORT=18000 bash install.sh     # 宿主机 8000 被占用时改端口
#   FORCE=1 bash install.sh            # 已有 .env 时也重新生成（会换密钥，慎用）
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "${HERE}"

info() { printf '\033[36m[安装]\033[0m %s\n' "$*"; }
die() { printf '\033[31m[失败]\033[0m %s\n' "$*" >&2; exit 1; }

# ── 1. 前置检查 ────────────────────────────────────────────────────────
info "检查 Docker 环境"
command -v docker >/dev/null 2>&1 || die "未找到 docker，请先安装 Docker"

# compose v2 插件与老版 docker-compose 二选一
if docker compose version >/dev/null 2>&1; then
    COMPOSE="docker compose"
elif command -v docker-compose >/dev/null 2>&1; then
    COMPOSE="docker-compose"
else
    die "未找到 docker compose（v2 插件）或 docker-compose，请先安装"
fi
info "使用编排命令：${COMPOSE}"

[ -f docker-compose.yml ] || die "缺少 docker-compose.yml，安装包可能不完整"

image_archive="$(ls -1 images/cenkormes_images_*.tar.gz 2>/dev/null | head -n 1 || true)"
[ -n "${image_archive}" ] || die "缺少镜像包 images/cenkormes_images_*.tar.gz"

version="$(tr -d '[:space:]' < VERSION 2>/dev/null || echo unknown)"
info "安装版本：${version}"

# ── 2. 导入镜像 ────────────────────────────────────────────────────────
info "导入镜像：${image_archive}（体积较大，请耐心等待）"
gunzip -c "${image_archive}" | docker load

# ── 3. 生成 .env ───────────────────────────────────────────────────────
if [ -f .env ] && [ "${FORCE:-0}" != "1" ]; then
    info "已存在 .env，保留现有配置（如需重建请设 FORCE=1）"
else
    info "生成 .env"
    cp .env.offline.example .env

    # 自动填一个强随机密钥，避免装完就是弱口令
    secret=""
    if command -v python3 >/dev/null 2>&1; then
        secret="$(python3 -c 'import secrets;print(secrets.token_urlsafe(48))')"
    elif command -v openssl >/dev/null 2>&1; then
        secret="$(openssl rand -base64 48 | tr -d '\n=+/' | cut -c1-64)"
    fi

    if [ -z "${secret}" ]; then
        die "无法生成随机密钥（缺 python3 / openssl）。请手工编辑 .env 填写 JWT_SECRET（≥32 位）"
    fi

    # 用 awk 写入，避免 sed 对特殊字符的处理差异
    awk -v s="${secret}" 'BEGIN{done=0} /^JWT_SECRET=/{print "JWT_SECRET=" s; done=1; next} {print} END{if(!done) print "JWT_SECRET=" s}' \
        .env > .env.tmp && mv .env.tmp .env
    chmod 600 .env
    info "已生成随机 JWT_SECRET 并写入 .env"
fi

# 允许命令行覆盖端口（不修改用户已有文件的其他内容）
if [ -n "${APP_PORT:-}" ]; then
    info "使用指定后端端口 APP_PORT=${APP_PORT}"
    awk -v p="${APP_PORT}" '/^APP_PORT=/{print "APP_PORT=" p; next} {print}' .env > .env.tmp && mv .env.tmp .env
fi

app_port="$(grep -E '^APP_PORT=' .env | tail -n 1 | cut -d= -f2 || echo 8000)"
app_port="${app_port:-8000}"

# ── 4. 启动 ────────────────────────────────────────────────────────────
info "启动全栈服务"
${COMPOSE} up -d

# ── 5. 等待后端健康 ────────────────────────────────────────────────────
info "等待后端就绪（最多 180s）"
ready=0
for i in $(seq 1 60); do
    if curl -fsS --max-time 3 "http://127.0.0.1:${app_port}/api/health" >/dev/null 2>&1; then
        ready=1
        info "后端已就绪（约 $((i * 3))s）"
        break
    fi
    sleep 3
done

if [ "${ready}" != "1" ]; then
    printf '\n'
    die "后端 180s 内未就绪。排查建议：
  1) ${COMPOSE} ps            查看容器状态
  2) ${COMPOSE} logs backend  查看后端日志
  3) 确认宿主机端口 ${app_port} 未被占用"
fi

# ── 6. 自检 ────────────────────────────────────────────────────────────
printf '\n'
if [ -f post-deploy-check.sh ]; then
    info "运行部署自检"
    # 容器部署没有 systemd 单元，跳过 celery 那一项（compose 自己托管）
    CENKORMES_HEALTH_URL="http://127.0.0.1:${app_port}/api/health" \
        SKIP_CELERY=1 bash post-deploy-check.sh || true
fi

cat <<EOF

============================================================
 CenkorMES ${version} 安装完成
------------------------------------------------------------
 管理后台：http://<主机IP>:$(grep -E '^WEB_ADMIN_PORT=' .env | cut -d= -f2)
 员工 H5 ：http://<主机IP>:$(grep -E '^WEB_H5_PORT=' .env | cut -d= -f2)
 后端 API：http://<主机IP>:${app_port}/docs

 默认管理员：admin / admin123（首次登录后请立即修改）
 配置文件：$(pwd)/.env

 停止：${COMPOSE} stop
 启动：${COMPOSE} start
 卸载（保留数据）：${COMPOSE} down
============================================================
EOF
