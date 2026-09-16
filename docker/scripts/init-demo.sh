#!/usr/bin/env bash
# 向已启动的 CenkorMES backend 容器注入完整演示数据（幂等，可重复执行）
#
# 用法（在一键部署的宿主机执行）：
#   bash docker/scripts/init-demo.sh                 # 自动探测 backend 容器
#   bash docker/scripts/init-demo.sh <容器名>        # 或手动指定
set -euo pipefail

CONTAINER="${1:-}"
if [ -z "$CONTAINER" ]; then
  CONTAINER="$(docker ps --filter 'ancestor=cenkormes-backend' --format '{{.Names}}' 2>/dev/null | head -1 || true)"
fi
if [ -z "$CONTAINER" ]; then
  CONTAINER="cenkormes-backend-1"
fi

echo "[cenkormes] 向容器 '${CONTAINER}' 注入演示数据（幂等）..."
docker exec "${CONTAINER}" sh -lc 'cd /app && python scripts/seed_demo.py'
echo "[cenkormes] 演示数据注入完成。演示账号密码：123456（admin 除外）。"