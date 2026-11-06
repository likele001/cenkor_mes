#!/usr/bin/env bash
# 制作 CenkorMES 完整离线部署包（在已成功 `docker compose build` 的构建机上执行）
#
# 与 docker/scripts/export-images.sh 的区别：
#   export-images.sh  只导出镜像 tar，配套文件要自己凑——客户机上容易漏 .env、
#                     拿到旧版 compose，或者根本不知道该放哪。
#   本脚本            产出一个自包含的 tar.gz：镜像 + compose + env 模板 +
#                     VERSION + 安装脚本 + 自检脚本 + MANIFEST + sha256。
#                     目标机解包后 `bash install.sh` 一条命令装完。
#
# 用法：
#   bash scripts/make-offline-bundle.sh              # 输出到 ./dist-offline
#   bash scripts/make-offline-bundle.sh /data/pkg    # 指定输出目录
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT_DIR="${1:-${ROOT}/dist-offline}"
VERSION="$(tr -d '[:space:]' < "${ROOT}/VERSION")"
STAMP="$(date +%Y%m%d_%H%M%S)"
BUNDLE_NAME="cenkormes-offline-${VERSION}-${STAMP}"

info() { printf '\033[36m[打包]\033[0m %s\n' "$*"; }
die() { printf '\033[31m[失败]\033[0m %s\n' "$*" >&2; exit 1; }

command -v docker >/dev/null 2>&1 || die "未找到 docker"
command -v sha256sum >/dev/null 2>&1 || die "未找到 sha256sum"

WORK="$(mktemp -d)"
trap 'rm -rf "${WORK}"' EXIT

# ── 1. 导出镜像 ────────────────────────────────────────────────────────
info "导出镜像（缺少镜像会在这里中止，先跑 docker compose build）"
bash "${ROOT}/docker/scripts/export-images.sh" "${WORK}/images"

image_archive="$(ls -1 "${WORK}"/images/cenkormes_images_*.tar.gz | head -n 1)"
[ -n "${image_archive}" ] || die "镜像导出失败"

# ── 2. 组装目录 ────────────────────────────────────────────────────────
info "组装包目录：${BUNDLE_NAME}"
BUNDLE="${WORK}/${BUNDLE_NAME}"
mkdir -p "${BUNDLE}/images"

cp "${image_archive}"                     "${BUNDLE}/images/"
cp "${ROOT}/docker-compose.yml"           "${BUNDLE}/"
cp "${ROOT}/.env.offline.example"         "${BUNDLE}/"
cp "${ROOT}/VERSION"                      "${BUNDLE}/"
cp "${ROOT}/scripts/offline-install.sh"   "${BUNDLE}/install.sh"
cp "${ROOT}/scripts/post-deploy-check.sh" "${BUNDLE}/"
chmod +x "${BUNDLE}/install.sh" "${BUNDLE}/post-deploy-check.sh"

# ── 3. MANIFEST ────────────────────────────────────────────────────────
info "生成 MANIFEST.txt"
{
    echo "CenkorMES 离线部署包"
    echo "===================="
    echo "版本      : ${VERSION}"
    echo "构建时间  : $(date '+%Y-%m-%d %H:%M:%S %Z')"
    echo "构建主机  : $(hostname)"
    echo "构建提交  : $(cd "${ROOT}" && git rev-parse --short HEAD 2>/dev/null || echo 'unknown')"
    echo
    echo "镜像清单（含 MySQL 8.0 / Redis 7）"
    echo "----------------------------------"
    for img in cenkormes-backend cenkormes-web-admin cenkormes-web-h5 mysql:8.0 redis:7-alpine; do
        echo "  ${img}"
    done
    echo
    echo "包含文件"
    echo "--------"
    echo "  images/$(basename "${image_archive}")"
    echo "  docker-compose.yml"
    echo "  .env.offline.example"
    echo "  install.sh"
    echo "  post-deploy-check.sh"
    echo "  VERSION"
    echo "  MANIFEST.txt"
    echo "  SHA256SUMS"
    echo
    echo "目标机安装步骤"
    echo "--------------"
    echo "  tar xzf ${BUNDLE_NAME}.tar.gz"
    echo "  cd ${BUNDLE_NAME}"
    echo "  bash install.sh"
} > "${BUNDLE}/MANIFEST.txt"

# ── 4. 校验清单 ────────────────────────────────────────────────────────
info "生成 SHA256SUMS"
(
    cd "${BUNDLE}"
    # 只对非镜像文件算哈希：镜像 tar 本身几十 GB，算一遍太慢，
    # 而且它是 docker save 的原始输出，完整性由外层 tar.gz 的 sha256 保证。
    sha256sum docker-compose.yml .env.offline.example install.sh post-deploy-check.sh VERSION MANIFEST.txt \
        > SHA256SUMS
)

# ── 5. 打包 ────────────────────────────────────────────────────────────
mkdir -p "${OUT_DIR}"
archive="${OUT_DIR}/${BUNDLE_NAME}.tar.gz"
info "打包 → ${archive}"
tar czf "${archive}" -C "${WORK}" "${BUNDLE_NAME}"

sha="$(sha256sum "${archive}" | awk '{print $1}')"
echo "${sha}  $(basename "${archive}")" > "${archive}.sha256"

echo
info "完成"
echo "  包路径   : ${archive}"
echo "  体积     : $(du -h "${archive}" | cut -f1)"
echo "  SHA256   : ${sha}"
echo
echo "交付给客户时把 .tar.gz 和 .tar.gz.sha256 一起给；"
echo "目标机先校验：sha256sum -c ${BUNDLE_NAME}.tar.gz.sha256"
