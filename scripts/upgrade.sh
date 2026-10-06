#!/usr/bin/env bash
# CenkorMES 升级脚本（自托管 / 裸机 / 宝塔）
# 作用：备份数据库 → 拉取新代码 → 更新依赖 → 执行 alembic 迁移 → 重建前端。
# 安全：本脚本绝不启停任何服务进程；重启由运维手动执行。
set -euo pipefail

# ---- 定位仓库根 ----
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
BACKEND="$ROOT/backend"
ENV_FILE="$BACKEND/.env"

# ---- 参数 ----
NO_PULL=0; DRY=0; SKIP_FE=0; TARGET=""
usage() {
  cat <<'EOF'
用法: scripts/upgrade.sh [选项]
  --target <ref>   升级到指定 git 引用（tag/分支/commit），默认按当前分支 pull
  --no-pull        跳过 git 拉取（代码已手动更新时用）
  --skip-frontend  跳过前端构建
  --dry-run        仅打印将执行的动作，不实际改动
  -h, --help       显示帮助
EOF
}
while [ $# -gt 0 ]; do
  case "$1" in
    --target) TARGET="${2:-}"; shift 2;;
    --no-pull) NO_PULL=1; shift;;
    --skip-frontend) SKIP_FE=1; shift;;
    --dry-run) DRY=1; shift;;
    -h|--help) usage; exit 0;;
    *) echo "未知参数: $1" >&2; usage; exit 1;;
  esac
done

log() { echo "==> $*"; }
run() { if [ "$DRY" = 1 ]; then echo "[dry-run] $*"; else "$@"; fi; }

# ---- 选择 Python 解释器（可用 PYTHON_BIN 显式指定生产 venv）----
if [ -n "${PYTHON_BIN:-}" ]; then PY="$PYTHON_BIN"
elif [ -x "$BACKEND/.venv/bin/python" ]; then PY="$BACKEND/.venv/bin/python"
elif [ -x "$BACKEND/venv/bin/python" ]; then PY="$BACKEND/venv/bin/python"
else PY="$(command -v python3 || true)"; fi
[ -n "$PY" ] || { echo "!! 未找到 python3，请先激活虚拟环境或设 PYTHON_BIN 指向生产 venv 的 python" >&2; exit 1; }
log "使用 Python: $PY"

cd "$BACKEND"

# ---- 1. 备份数据库（从 .env 解析 DB_URL）----
DB_URL=""
[ -f "$ENV_FILE" ] && DB_URL="$(grep -E '^DB_URL=' "$ENV_FILE" | head -1 | cut -d= -f2- || true)"
if [ -n "$DB_URL" ] && [ "${DB_URL#mysql}" != "$DB_URL" ]; then
  _rest="${DB_URL#*://}"                 # user:pass@host:port/db?charset
  _cred="${_rest%%@*}"                   # user:pass
  _hpdb="${_rest#*@}"                    # host:port/db?...
  DB_USER="${_cred%%:*}"
  DB_PASS="${_cred#*:}"
  _hp="${_hpdb%%/*}"                     # host:port
  DB_HOST="${_hp%%:*}"
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
  log "未从 .env 解析到 MySQL DB_URL，跳过自动备份（请自行确保已备份！）"
fi

# ---- 2. 拉取代码 ----
if [ "$NO_PULL" = 0 ]; then
  cd "$ROOT"
  if [ -n "$(git status --porcelain)" ]; then
    echo "!! 工作树不干净：请先提交/暂存，或用 --no-pull 跳过拉取" >&2; exit 1
  fi
  log "git fetch --tags"
  run git fetch --tags
  if [ -n "$TARGET" ]; then
    log "checkout $TARGET"
    run git checkout "$TARGET"
  else
    BR="$(git rev-parse --abbrev-ref HEAD)"
    log "pull --ff-only origin $BR"
    run git pull --ff-only origin "$BR"
  fi
  cd "$BACKEND"
fi

# ---- 3. 后端依赖 ----
log "安装/更新后端依赖 (pip install -r requirements.txt)"
run "$PY" -m pip install -r requirements.txt

# ---- 4. 数据库迁移（先迁移，后启动）----
log "执行 alembic 迁移 (upgrade head)"
run "$PY" -m alembic upgrade head
if [ "$DRY" != 1 ]; then
  log "当前库版本: $("$PY" -m alembic current 2>/dev/null | tail -1)"
fi

# ---- 5. 前端构建 ----
if [ "$SKIP_FE" = 0 ]; then
  for fe in frontend-admin-pro frontend-h5; do
    d="$ROOT/$fe"
    if [ -d "$d" ] && [ -f "$d/package.json" ]; then
      log "构建前端 $fe"
      if [ "$DRY" = 1 ]; then
        echo "[dry-run] (cd $d && npm ci && npm run build)"
      else
        (cd "$d" && npm ci --prefer-offline --no-audit --no-fund && npm run build)
      fi
    fi
  done
fi

# ---- 6. 重启提示（脚本不重启）----
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
