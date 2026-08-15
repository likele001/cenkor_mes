#!/usr/bin/env bash
# cenkormes 一键发布：版本号递增 → 追加开发日志到 backend/CHANGELOG.json → 提交并推送
# 用法:
#   bash scripts/release-all.sh "更新说明"
#   VERSION_BUMP=minor bash scripts/release-all.sh "更新说明"   # minor 递增: v1.0.0 → v1.1.0
#   VERSION_BUMP=major bash scripts/release-all.sh "更新说明"   # major 递增: v1.0.0 → v2.0.0
#   bash scripts/release-all.sh --dry-run "更新说明"            # 试跑，不写文件、不提交、不推送
#   bash scripts/release-all.sh --no-push "更新说明"            # 仅本地提交，不推送 GitHub
#
# 说明:
#   - 版本号唯一数据源为根目录 VERSION 文件（当前 v1.0.0）。
#   - 每次发布会把说明追加进 backend/CHANGELOG.json（按版本号幂等：同版本号覆盖描述）。
#   - 后端 main.py 在【启动时】把 CHANGELOG.json 同步进 system_versions 表，
#     因此发布后必须【在宝塔面板重启 cenkormes 后端】，关于页才会显示新版本。
#   - 本脚本不导出社区版/专业版（cenkormes 为单仓，无 lightmes 那套双仓拆分）。
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
VERSION_FILE="$ROOT/VERSION"
CHANGELOG_FILE="$ROOT/backend/CHANGELOG.json"

DRY_RUN=0
NO_PUSH=0
COMMITS=()

for arg in "$@"; do
  case "$arg" in
    --dry-run)  DRY_RUN=1 ;;
    --no-push)  NO_PUSH=1 ;;
    *)          COMMITS+=("$arg") ;;
  esac
done

if [[ ${#COMMITS[@]} -eq 0 ]]; then
  echo "用法: bash scripts/release-all.sh \"更新说明\""
  echo "示例: bash scripts/release-all.sh \"修复报工审核逻辑\""
  echo "试跑: bash scripts/release-all.sh --dry-run \"更新说明\""
  echo "不推送: bash scripts/release-all.sh --no-push \"更新说明\""
  exit 1
fi

_run() {
  if [[ "$DRY_RUN" -eq 1 ]]; then
    echo "[dry-run] $*"
  else
    "$@"
  fi
}

cd "$ROOT"

# ---- 版本号自动递增 ----
CURRENT_VER="$(cat "$VERSION_FILE" 2>/dev/null || echo "v0.0.0")"
VER_NUM="${CURRENT_VER#v}"
MAJOR="${VER_NUM%%.*}"
REST="${VER_NUM#*.}"
MINOR="${REST%%.*}"
PATCH="${REST##*.}"
BUMP="${VERSION_BUMP:-patch}"
case "$BUMP" in
  major) NEW_VER="v$((MAJOR+1)).0.0" ;;
  minor) NEW_VER="v$MAJOR.$((MINOR+1)).0" ;;
  *)     NEW_VER="v$MAJOR.$MINOR.$((PATCH+1))" ;;
esac
echo "==> 版本号: $CURRENT_VER → $NEW_VER"
if [[ "$DRY_RUN" -eq 1 ]]; then
  echo "[dry-run] echo $NEW_VER > $VERSION_FILE"
else
  echo "$NEW_VER" > "$VERSION_FILE"
fi

# ---- 追加开发日志到 CHANGELOG.json ----
CHANGE_DESC="${COMMITS[0]}"
for ((i = 1; i < ${#COMMITS[@]}; i++)); do
  CHANGE_DESC="${CHANGE_DESC}；${COMMITS[$i]}"
done
TODAY="$(date +%Y-%m-%d)"
echo "==> 开发日志: [$NEW_VER] $CHANGE_DESC"
if [[ "$DRY_RUN" -eq 1 ]]; then
  echo "[dry-run] 追加 $NEW_VER / $TODAY 到 $CHANGELOG_FILE"
else
  python3 - "$CHANGELOG_FILE" "$NEW_VER" "$TODAY" "$CHANGE_DESC" <<'PYEOF'
import json
import sys

path, ver, today, desc = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4]
try:
    with open(path, "r", encoding="utf-8") as f:
        rows = json.load(f)
except (FileNotFoundError, json.JSONDecodeError):
    rows = []
# 幂等：已存在同版本号则替换描述
rows = [r for r in rows if r.get("version") != ver]
rows.append({"version": ver, "release_date": today, "description": desc})
rows.sort(key=lambda r: r.get("release_date", ""))
with open(path, "w", encoding="utf-8") as f:
    json.dump(rows, f, ensure_ascii=False, indent=2)
    f.write("\n")
PYEOF
fi

# ---- 提交并推送 ----
BRANCH="$(git symbolic-ref --short HEAD)"
echo "==> 提交 VERSION + CHANGELOG 到 $BRANCH"
if git diff --quiet "$VERSION_FILE" "$CHANGELOG_FILE" 2>/dev/null; then
  echo "    版本文件无变化，跳过提交"
else
  _run git add "$VERSION_FILE" "$CHANGELOG_FILE"
  _run git commit -m "chore(release): bump version to $NEW_VER" -m "$CHANGE_DESC"
fi

if [[ "$DRY_RUN" -eq 0 && "$NO_PUSH" -eq 0 ]]; then
  _run git push -u origin "$BRANCH"
  echo "✅ 已推送到 origin/$BRANCH"
elif [[ "$NO_PUSH" -eq 1 && "$DRY_RUN" -eq 0 ]]; then
  echo "（--no-push）已本地提交，未推送。需要时手动: git push -u origin $BRANCH"
fi

echo "========================================"
echo " 发布完成: $NEW_VER"
echo " ⚠️ 请到宝塔面板重启 cenkormes 后端，关于页才会显示新版本"
echo "========================================"
