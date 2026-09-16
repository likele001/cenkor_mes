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

exec "$@"