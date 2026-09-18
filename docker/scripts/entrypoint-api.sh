#!/usr/bin/env bash
# CenkorMES 后端容器入口：
#   1. 等待 MySQL 就绪（避免启动竞态）
#   2. 建表 / 默认管理员由应用自身 startup 事件在 DB_AUTO_CREATE / DB_AUTO_SEED 为真时完成
#   3. exec 透传 CMD（uvicorn app.main:app --port 8000）
set -euo pipefail

DB_HOST="${DB_HOST:-mysql}"
DB_PORT="${DB_PORT:-3306}"

echo "[cenkormes] 等待 MySQL ${DB_HOST}:${DB_PORT} 就绪 ..."
python - "${DB_HOST}" "${DB_PORT}" <<'PYEOF'
import socket, sys, time
host, port = sys.argv[1], int(sys.argv[2])
for _ in range(60):
    try:
        with socket.create_connection((host, port), timeout=3):
            sys.exit(0)
    except OSError:
        time.sleep(2)
print("MySQL 在 120s 内未就绪", file=sys.stderr)
sys.exit(1)
PYEOF
echo "[cenkormes] MySQL 已就绪，启动后端 ..."

# 生产 + 未配置安全 JWT_SECRET 时，兜底生成临时强随机密钥，保证一键启动开箱即用。
# 判定复用应用自身的 ensure_secure_jwt_secret（黑名单 / 最短长度一致）。
if [ "${APP_ENV:-prod}" = "prod" ]; then
  if ! python -c 'from app.core.security import ensure_secure_jwt_secret; ensure_secure_jwt_secret()' 2>/dev/null; then
    export JWT_SECRET="$(python -c 'import secrets; print(secrets.token_urlsafe(48))')"
    echo "[cenkormes][WARN] 未配置安全的 JWT_SECRET，已临时生成随机密钥（重启容器后失效）。"
    echo "[cenkormes][WARN] 正式部署请设置固定强密钥：在仓库根 .env 设置 JWT_SECRET 后重新 docker compose up -d。"
  fi
fi

exec "$@"