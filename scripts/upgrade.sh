#!/usr/bin/env bash
# CenkorMES 升级脚本（自托管 / 裸机 / 宝塔）
#
# 两种模式：
#   artifact（默认）：从 GitHub Release 下载发布产物包，校验 SHA256 后覆盖安装。
#                     客户机不需要 git、不需要 SSH key、也不需要 node——包里
#                     已带预构建的前端 dist。这是产品分发的正式通道。
#   git    （--git）：git fetch + checkout，只在「开发机即部署机」时用。
#
# 流程：备份数据库 → 取产物包并校验 → 覆盖代码 → 更新依赖 → alembic 迁移 → 提示重启。
# 安全：本脚本绝不启停任何服务进程；重启由运维手动执行。
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
BACKEND="$ROOT/backend"
ENV_FILE="$BACKEND/.env"

MODE="artifact"; VERSION=""; LIST=0; DRY=0; SKIP_FE=0; SKIP_BACKUP=0; TARGET=""
REPO="${CENKORMES_REPO:-likele001/cenkor_mes}"
API="${CENKORMES_GITHUB_API:-https://api.github.com}"

usage() {
  cat <<'EOF'
用法: scripts/upgrade.sh [选项]

产物包模式（默认，客户机用）:
  --version <vX.Y.Z>  安装指定版本，省略则取最新正式版
  --list              列出远端可安装的版本后退出
  --skip-frontend     不换入前端 dist（正常不需要，包内已含）
  --skip-backup       跳过数据库备份（不推荐）
  --repo <owner/name> 指定 GitHub 仓库，默认 likele001/cenkor_mes

git 模式（仅开发机）:
  --git               改用 git fetch + checkout
  --target <ref>      git 模式下指定引用（tag/分支/commit）

通用:
  --dry-run           仅打印将执行的动作，不实际改动
  -h, --help          显示帮助
EOF
}

while [ $# -gt 0 ]; do
  case "$1" in
    --version) VERSION="${2:-}"; shift 2;;
    --list) LIST=1; shift;;
    --git) MODE="git"; shift;;
    --target) TARGET="${2:-}"; shift 2;;
    --repo) REPO="${2:-}"; shift 2;;
    --skip-frontend) SKIP_FE=1; shift;;
    --skip-backup) SKIP_BACKUP=1; shift;;
    --dry-run) DRY=1; shift;;
    -h|--help) usage; exit 0;;
    *) echo "未知参数: $1" >&2; usage; exit 1;;
  esac
done

log()  { echo "==> $*"; }
warn() { echo "!! $*" >&2; }
run()  { if [ "$DRY" = 1 ]; then echo "[dry-run] $*"; else "$@"; fi; }

# ---- Python 解释器（可用 PYTHON_BIN 显式指定生产 venv）----
if [ -n "${PYTHON_BIN:-}" ]; then PY="$PYTHON_BIN"
elif [ -x "$BACKEND/.venv/bin/python" ]; then PY="$BACKEND/.venv/bin/python"
elif [ -x "$BACKEND/venv/bin/python" ]; then PY="$BACKEND/venv/bin/python"
else PY="$(command -v python3 || true)"; fi
[ -n "$PY" ] || { warn "未找到 python3，请先激活虚拟环境或设 PYTHON_BIN 指向生产 venv 的 python"; exit 1; }

# ---- 版本查询：解析 GitHub Releases（公开仓库，匿名即可）----
# 输出每个可用版本一行：「版本 包地址 摘要地址」
list_releases() {
  REPO="$REPO" API="$API" "$PY" - <<'PY'
import json, os, re, sys, urllib.request

repo, api = os.environ["REPO"], os.environ["API"].rstrip("/")
req = urllib.request.Request(
    f"{api}/repos/{repo}/releases?per_page=30",
    headers={"Accept": "application/vnd.github+json", "User-Agent": "cenkormes-upgrade"},
)
try:
    rows = json.load(urllib.request.urlopen(req, timeout=30))
except Exception as exc:                     # noqa: BLE001 - 统一转成可读错误
    print(f"ERROR {exc}", file=sys.stderr); sys.exit(2)

out = []
for rel in rows:
    tag = (rel.get("tag_name") or "").strip()
    if not re.fullmatch(r"v\d+\.\d+\.\d+", tag) or rel.get("draft") or rel.get("prerelease"):
        continue
    pkg = sha = ""
    for a in rel.get("assets") or []:
        name = a.get("name") or ""
        if name.endswith(".tar.gz"):
            pkg = a.get("browser_download_url") or ""
        elif name.endswith(".sha256"):
            sha = a.get("browser_download_url") or ""
    if pkg:
        out.append((tuple(int(x) for x in tag.lstrip("v").split(".")), tag, pkg, sha))
out.sort()
for _, tag, pkg, sha in out:
    print(tag, pkg, sha or "-")
PY
}

if [ "$LIST" = 1 ]; then
  log "仓库 $REPO 可安装版本（含产物包）"
  list_releases | awk '{print "  " $1}'
  exit 0
fi

# ---- 1. 备份数据库 ----
if [ "$SKIP_BACKUP" = 1 ]; then
  log "已按 --skip-backup 跳过数据库备份"
else
  DB_URL=""
  [ -f "$ENV_FILE" ] && DB_URL="$(grep -E '^DB_URL=' "$ENV_FILE" | head -1 | cut -d= -f2- || true)"
  if [ -n "$DB_URL" ] && [ "${DB_URL#mysql}" != "$DB_URL" ]; then
    _rest="${DB_URL#*://}"; _cred="${_rest%%@*}"; _hpdb="${_rest#*@}"
    DB_USER="${_cred%%:*}"; DB_PASS="${_cred#*:}"
    _hp="${_hpdb%%/*}"; DB_HOST="${_hp%%:*}"
    DB_PORT="${_hp##*:}"; [ "$DB_PORT" = "$_hp" ] && DB_PORT=3306
    _dbq="${_hpdb#*/}"; DB_NAME="${_dbq%%\?*}"
    BAK_DIR="$BACKEND/data/backups"; mkdir -p "$BAK_DIR"
    BAK="$BAK_DIR/${DB_NAME}_preupgrade_$(date +%F_%H%M%S).sql.gz"
    log "备份数据库 $DB_NAME -> $BAK"
    if [ "$DRY" = 1 ]; then
      echo "[dry-run] mysqldump ... | gzip > $BAK"
    else
      MYSQL_PWD="$DB_PASS" mysqldump -h"$DB_HOST" -P"$DB_PORT" -u"$DB_USER" \
        --default-character-set=utf8mb4 --single-transaction --routines --events "$DB_NAME" | gzip > "$BAK"
      log "备份完成: $(du -h "$BAK" | cut -f1)"
    fi
  else
    warn "未从 .env 解析到 MySQL DB_URL，跳过自动备份（请自行确保已备份！）"
  fi
fi

# ================= git 模式（开发机）=================
if [ "$MODE" = "git" ]; then
  cd "$ROOT"
  if [ -n "$(git status --porcelain)" ]; then
    warn "工作树不干净：请先提交/暂存后再升级"; exit 1
  fi
  log "git fetch --tags"
  run git fetch --tags
  if [ -n "$TARGET" ]; then
    log "checkout $TARGET"; run git checkout "$TARGET"
  else
    BR="$(git rev-parse --abbrev-ref HEAD)"
    log "pull --ff-only origin $BR"; run git pull --ff-only origin "$BR"
  fi

  cd "$BACKEND"
  log "安装/更新后端依赖"; run "$PY" -m pip install -r requirements.txt
  log "执行 alembic 迁移"; run "$PY" -m alembic upgrade head
  if [ "$SKIP_FE" = 0 ]; then
    for fe in frontend-admin-pro frontend-h5; do
      d="$ROOT/$fe"
      if [ -d "$d" ] && [ -f "$d/package.json" ]; then
        # git 模式不重建前端会出现「代码已更新、页面还是旧的」；包模式才不需要 node
        command -v npm >/dev/null || { warn "$fe 需要 npm 构建，请安装 node 或改用产物包模式"; exit 1; }
        log "构建前端 $fe"
        run bash -c "cd '$d' && npm ci --prefer-offline --no-audit --no-fund && npm run build"
      fi
    done
  fi
else
  # ================= 产物包模式（客户机）=================
  log "模式：产物包（仓库 $REPO），无需 git / SSH / node"

  RELS="$(list_releases)" || { warn "获取版本列表失败，请检查网络或 --repo 是否正确"; exit 1; }
  [ -n "$RELS" ] || { warn "仓库 $REPO 没有带产物包的正式 Release"; exit 1; }

  if [ -n "$VERSION" ]; then
    LINE="$(printf '%s\n' "$RELS" | awk -v v="$VERSION" '$1==v')"
    [ -n "$LINE" ] || { warn "没有找到 $VERSION 的产物包；可用版本："; printf '%s\n' "$RELS" | awk '{print "  " $1}'; exit 1; }
  else
    LINE="$(printf '%s\n' "$RELS" | tail -1)"
    VERSION="$(printf '%s' "$LINE" | awk '{print $1}')"
  fi
  PKG_URL="$(printf '%s' "$LINE" | awk '{print $2}')"
  SHA_URL="$(printf '%s' "$LINE" | awk '{print $3}')"

  CUR="$( { cat "$ROOT/VERSION" 2>/dev/null || echo unknown; } | tr -d ' \r\n')"
  CUR="${CUR:-unknown}"
  log "当前版本 $CUR → 目标版本 $VERSION"
  if [ "$CUR" = "$VERSION" ]; then
    log "已是指定版本，仍需覆盖安装（用于修复被改坏的文件）"
  fi

  TMP="$(mktemp -d /tmp/cenkormes-upgrade.XXXXXX)"
  trap 'rm -rf "$TMP"' EXIT

  log "下载 $PKG_URL"
  if [ "$DRY" = 1 ]; then
    echo "[dry-run] curl -fL -o $TMP/pkg.tar.gz $PKG_URL"
  else
    curl -fL --retry 3 --connect-timeout 20 -o "$TMP/pkg.tar.gz" "$PKG_URL"
    if [ "$SHA_URL" != "-" ]; then
      curl -fL --retry 3 --connect-timeout 20 -o "$TMP/pkg.sha256" "$SHA_URL"
      # .sha256 里写的是发版时的文件名，这里改成本地文件名再校验
      EXPECT="$(awk '{print $1}' "$TMP/pkg.sha256" | head -1)"
      ACTUAL="$(sha256sum "$TMP/pkg.tar.gz" | awk '{print $1}')"
      if [ "$EXPECT" != "$ACTUAL" ]; then
        warn "SHA256 校验失败：期望 ${EXPECT:0:16}… 实际 ${ACTUAL:0:16}…"; exit 1
      fi
      log "SHA256 校验通过：${ACTUAL:0:16}…"
    else
      warn "该 Release 未提供 .sha256 摘要，跳过完整性校验"
    fi

    log "解包"
    mkdir -p "$TMP/pkg"
    tar xzf "$TMP/pkg.tar.gz" -C "$TMP/pkg"
    PKGROOT="$(find "$TMP/pkg" -maxdepth 2 -name VERSION -printf '%h\n' | head -1)"
    [ -n "$PKGROOT" ] || { warn "产物包结构异常：找不到 VERSION"; exit 1; }
    PKG_VER="$(tr -d ' \r\n' < "$PKGROOT/VERSION")"
    [ "$PKG_VER" = "$VERSION" ] || { warn "包内 VERSION=$PKG_VER 与目标 $VERSION 不一致"; exit 1; }

    # 覆盖前清掉包内不该存在的东西，避免把现场配置/数据写进项目
    rm -rf "$PKGROOT/backend/data" "$PKGROOT/.git" "$PKGROOT/backend/.env" "$PKGROOT/.env"
    find "$PKGROOT" -name node_modules -type d -prune -exec rm -rf {} + 2>/dev/null || true
    find "$PKGROOT" \( -name '.env' -o -name '.env.*' \) -type f -delete 2>/dev/null || true

    if [ "$SKIP_FE" = 1 ]; then
      rm -rf "$PKGROOT/frontend-admin-pro/dist" "$PKGROOT/frontend-h5/dist"
      log "按 --skip-frontend 保留线上现有前端产物"
    fi

    log "覆盖代码到 $ROOT（保留 .env、backend/data、node_modules）"
    # 用 tar 管道覆盖：保留未包含的文件，不删除客户自己的东西
    ( cd "$PKGROOT" && tar -c . ) | ( cd "$ROOT" && tar -x --no-same-owner --no-overwrite-dir )
    log "代码已更新，VERSION=$(tr -d ' \r\n' < "$ROOT/VERSION")"
  fi

  cd "$BACKEND"
  log "安装/更新后端依赖"
  run "$PY" -m pip install -r requirements.txt
  log "执行 alembic 迁移"
  run "$PY" -m alembic upgrade head
  if [ "$DRY" != 1 ]; then
    log "当前库版本: $("$PY" -m alembic current 2>/dev/null | tail -1)"
  fi
fi

cat <<'EOF'

==============================================
 ✅ 升级准备完成（代码 / 依赖 / 数据库 / 前端）
 ⚠️  本脚本不会重启任何服务。
 请手动重启后端进程（uvicorn / celery）以加载新代码与版本：
   - 宝塔：面板中重启 cenkormes Python 项目
   - 裸机：kill 旧进程后按原方式重新启动
 重启后到「关于/版本」页确认版本号已更新。
==============================================
EOF
