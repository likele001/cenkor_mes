#!/usr/bin/env bash
# CenkorMES 全栈镜像离线导出（含 MySQL / Redis 基础镜像）
#
# 用法（在已成功 `docker compose build` 的构建机上）：
#   bash docker/scripts/export-images.sh                # 导出到 ./dist-images
#   bash docker/scripts/export-images.sh /data/pkg      # 指定输出目录
#
# 目标机（无外网 / 内网部署）导入：
#   docker load < dist-images/cenkormes_images_*.tar.gz
#   docker compose up -d         # 无需再联网拉取 / 构建
set -euo pipefail

OUT_DIR="${1:-dist-images}"
mkdir -p "$OUT_DIR"
stamp="$(date +%Y%m%d_%H%M%S)"

images=(
  cenkormes-backend
  cenkormes-web-admin
  cenkormes-web-h5
  mysql:8.0
  redis:7-alpine
)

missing=0
for img in "${images[@]}"; do
  if ! docker image inspect "$img" >/dev/null 2>&1; then
    echo "[cenkormes] 缺少镜像: ${img}（请先执行 docker compose build）"
    missing=1
  fi
done
if [ "$missing" -ne 0 ]; then
  echo "[cenkormes] 存在缺失镜像，中止导出。"
  exit 1
fi

archive="${OUT_DIR}/cenkormes_images_${stamp}.tar.gz"
echo "[cenkormes] 导出 ${#images[@]} 个镜像 → ${archive} ..."
docker save "${images[@]}" | gzip -9 > "$archive"
echo "[cenkormes] 导出完成，大小：$(du -h "$archive" | cut -f1)"
echo
echo "目标机导入命令："
echo "  docker load < ${archive}"
echo "  docker compose up -d"
echo "[cenkormes] 完成。"