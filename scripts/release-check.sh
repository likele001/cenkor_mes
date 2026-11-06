#!/usr/bin/env bash
# =============================================================
# CenkorMES 版本一致性自检（只读，不改任何文件）
#
# 为什么要有这个脚本：
#   VERSION 与 backend/CHANGELOG.json 是「同一件事的两半」——
#   VERSION 决定 tag 与 About 页版本号，CHANGELOG.json 决定 GitHub
#   Release 正文（release.yml 按 tag 去里面取 description）。
#   两处不同步时，tag 照样能推、Release 照样能建，但正文会退化成
#   "Release v2.2.1" 这种空壳，而 About 页显示的是新版本号。
#   这种事一旦发生，只有翻 GitHub 才发现，所以必须在推 tag 前拦住。
#
# 用法：
#   bash scripts/release-check.sh                    # 校验当前仓库的 VERSION
#   bash scripts/release-check.sh --tag v2.2.1       # 同时校验 tag 与 VERSION 一致
#   bash scripts/release-check.sh --root /path/repo  # 校验指定目录（CI 回填旧版本用）
#   bash scripts/release-check.sh --quiet            # 只输出错误
#   bash scripts/release-check.sh --impact           # 额外校验「升级影响」是否已声明
#
# 关于 --root：
#   CI 里校验「历史 tag」时必须用这个参数。因为回填旧版本时，checkout 到的是
#   旧 tag，而旧 tag 里可能还没有本脚本；所以 CI 从主干取脚本、用 --root 指向
#   目标 tag 的检出目录。脚本自身位置与实际校验目录解耦。
#
# 关于 --impact（2026-11-06 加，v2.2.16 教训）：
#   说明里只要出现金额类字样（税额/税率/金额/折扣/汇率的），就必须同时出现
#   「升级影响」四字，明确回答「老数据和老集成会不会变」。不要求结论正确，
#   要求的是**表态**——写「升级影响：无（纯展示修复）」也算通过。
#   默认关闭，原因：回填历史版本时旧描述必然没有这个标记，强校验会一条都过不了。
#   本地发版（release-all.sh）与 CI 推 tag 时显式打开，回填时不打开。
#
# 退出码：0 一致；1 不一致或数据缺失。
# =============================================================
set -uo pipefail

# 脚本自身位置推导的默认仓库根（--root 可覆盖）
SELF_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; DIM='\033[2m'; NC='\033[0m'
QUIET=0
TAG_INPUT=""
ROOT_INPUT=""
CHECK_IMPACT=0

while [ $# -gt 0 ]; do
  case "$1" in
    --quiet) QUIET=1 ;;
    --impact) CHECK_IMPACT=1 ;;
    --tag) TAG_INPUT="${2:-}"; shift ;;
    --root) ROOT_INPUT="${2:-}"; shift ;;
    -h|--help) sed -n '2,/^# 退出码/p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "未知参数: $1" >&2; exit 1 ;;
  esac
  shift
done

# ---- 确定校验目标目录 ----
if [ -n "$ROOT_INPUT" ]; then
  if ! ROOT="$(cd "$ROOT_INPUT" 2>/dev/null && pwd)"; then
    echo -e "${RED}✗ --root 指定的目录不存在：$ROOT_INPUT${NC}" >&2
    exit 1
  fi
else
  ROOT="$SELF_ROOT"
fi

VERSION_FILE="$ROOT/VERSION"
CHANGELOG_FILE="$ROOT/backend/CHANGELOG.json"

say()  { [ "$QUIET" = 1 ] || echo "$@"; }
fail() { echo -e "${RED}✗ $*${NC}" >&2; FAILED=1; }
FAILED=0
# 升级影响检查用；CHANGELOG 校验成功后会覆盖。默认 mark=1 表示「已表态」，
# 这样 CHANGELOG 缺失/解析失败时不会在已被 fail 的情况下再叠一条误报。
IMP_HITS=""
IMP_MARK="1"

say "校验目录: $ROOT"

# ---- 1. VERSION 文件 ----
if [ ! -f "$VERSION_FILE" ]; then
  fail "VERSION 文件不存在：$VERSION_FILE"
  exit 1
fi
# Windows 上 core.autocrlf=true 会让工作区文件变成 CRLF，读出 "v2.2.0\r"，
# 后面所有字符串比较都会失败且极难排查，这里统一清掉空白与回车。
VERSION="$(tr -d ' \r\n' < "$VERSION_FILE")"
say "VERSION      : ${VERSION:-（空）}"

if ! printf '%s' "$VERSION" | grep -Eq '^v[0-9]+\.[0-9]+\.[0-9]+$'; then
  fail "VERSION 格式不合法：「$VERSION」，应形如 v2.2.1"
fi

# ---- 2. CHANGELOG.json 条目 ----
if [ ! -f "$CHANGELOG_FILE" ]; then
  fail "backend/CHANGELOG.json 不存在"
else
  # 用 python 解析，避免 jq 依赖（客户环境不一定装）
  if ! RESULT="$(python3 - "$CHANGELOG_FILE" "$VERSION" <<'PY'
import json
import sys

path, want = sys.argv[1], sys.argv[2]
try:
    with open(path, encoding="utf-8") as f:
        rows = json.load(f)
except json.JSONDecodeError as exc:
    print(f"PARSE_ERROR|{exc}")
    raise SystemExit(0)

if not isinstance(rows, list):
    print("PARSE_ERROR|顶层不是数组")
    raise SystemExit(0)

hit = next((r for r in rows if str(r.get("version", "")).strip() == want), None)
if hit is None:
    print(f"MISSING|{len(rows)}")
else:
    desc = str(hit.get("description", "") or "").strip()
    date = str(hit.get("release_date", "") or "").strip()
    # 金额/计价类敏感词：命中即要求说明里有「升级影响」表态。
    # 只用作触发条件，不判断结论对错——写了「升级影响：无」同样通过。
    SENSITIVE = ("税额", "税率", "含税", "金额", "小计", "合计", "折扣",
                 "汇率", "单价", "计价", "默认值", "重算", "迁移")
    hits = [w for w in SENSITIVE if w in desc]
    mark = "1" if "升级影响" in desc else "0"
    print(f"OK|{len(desc)}|{date}|{','.join(hits)}|{mark}")
PY
)"; then
    fail "解析 CHANGELOG.json 失败（python3 不可用？）"
  else
    case "$RESULT" in
      PARSE_ERROR*)
        fail "CHANGELOG.json 不是合法 JSON 数组：${RESULT#PARSE_ERROR|}" ;;
      MISSING*)
        fail "CHANGELOG.json 里没有 $VERSION 条目（现有 ${RESULT#MISSING|} 条）——Release 正文会是空壳" ;;
      OK*)
        DESC_LEN="$(echo "$RESULT" | cut -d'|' -f2)"
        REL_DATE="$(echo "$RESULT" | cut -d'|' -f3)"
        IMP_HITS="$(echo "$RESULT" | cut -d'|' -f4)"
        IMP_MARK="$(echo "$RESULT" | cut -d'|' -f5)"
        if [ "${DESC_LEN:-0}" -lt 8 ]; then
          fail "CHANGELOG.json 中 $VERSION 的 description 过短（${DESC_LEN} 字），等于没写说明"
        else
          say "CHANGELOG    : $VERSION（$REL_DATE，说明 ${DESC_LEN} 字）"
        fi ;;
      *)
        fail "CHANGELOG 校验返回未知结果：$RESULT" ;;
    esac
  fi
fi

# ---- 3. 升级影响声明（仅 --impact 时校验）----
# 来自 v2.2.16 的真实教训：报价单税额从单据级改成按行税率合计，Release 正文
# 却写成「含税总额偏高」的纯 bug 修复，只字未提「历史单据不会自动重算」。
# 客户升级后新旧口径并存、对账对不上，第一反应就是「升级把数据搞乱了」。
#
# 这里不判断结论是否正确——那需要人懂业务；只强制表态：一旦说明里出现金额/
# 计价类字样，就必须回答「老数据和老集成会不会变」，写「无影响」也算通过。
# 默认关闭：回填历史版本时旧描述必然没有这个标记，强校验会一条都过不了。
if [ "$CHECK_IMPACT" = 1 ]; then
  if [ -n "${IMP_HITS}" ] && [ "${IMP_MARK}" != "1" ]; then
    fail "$VERSION 的说明涉及金额/计价口径（命中：${IMP_HITS}），但未声明升级影响"
    {
      echo "    说明里必须明确回答「老数据和老集成会不会变」，两种写法都通过："
      echo "      · 会变 → 「【升级影响】哪类数据会变 / 哪类不变 / 历史数据是否自动重算」"
      echo "      · 不变 → 「升级影响：无（纯展示修复，计算结果不变）」"
      echo "    只要求表态，不要求结论正确。改 backend/CHANGELOG.json 里 $VERSION 的 description。"
    } >&2
  elif [ -n "${IMP_HITS}" ]; then
    say "升级影响     : 已声明（说明涉及 ${IMP_HITS}）"
  else
    say -e "${DIM}升级影响     : 未涉及金额/计价类字样，跳过${NC}"
  fi
fi

# ---- 4. tag 一致性（CI 传入 --tag，本地不传则跳过） ----
if [ -n "$TAG_INPUT" ]; then
  say "TAG          : $TAG_INPUT"
  if [ "$TAG_INPUT" != "$VERSION" ]; then
    fail "tag「$TAG_INPUT」与 VERSION「$VERSION」不一致——打错 tag 或忘了 bump 版本"
  fi
fi

# ---- 5. 工作区状态（仅提示，不判失败） ----
if command -v git >/dev/null 2>&1 && [ -d "$ROOT/.git" ]; then
  DIRTY="$(git -C "$ROOT" status --porcelain --untracked-files=no 2>/dev/null | head -5)"
  if [ -n "$DIRTY" ]; then
    [ "$QUIET" = 1 ] || {
      echo -e "${YELLOW}⚠ 工作区有未提交改动（不影响本次校验，但发布前建议先提交）：${NC}"
      echo "$DIRTY" | sed 's/^/    /'
    }
  fi
  # 若该版本 tag 已存在，提示它指向的 commit 是否就是 HEAD
  if git -C "$ROOT" rev-parse -q --verify "refs/tags/$VERSION" >/dev/null 2>&1; then
    TAG_SHA="$(git -C "$ROOT" rev-parse "refs/tags/$VERSION^{commit}" 2>/dev/null)"
    HEAD_SHA="$(git -C "$ROOT" rev-parse HEAD 2>/dev/null)"
    if [ "$TAG_SHA" != "$HEAD_SHA" ]; then
      say -e "${DIM}提示: tag $VERSION 已存在，指向 ${TAG_SHA:0:8}（HEAD 是 ${HEAD_SHA:0:8}）${NC}"
    else
      say -e "${DIM}提示: tag $VERSION 已存在且指向 HEAD${NC}"
    fi
  fi
fi

# ---- 结果 ----
if [ "$FAILED" -ne 0 ]; then
  echo -e "${RED}版本一致性校验未通过${NC}" >&2
  echo "  修复：把说明补进 backend/CHANGELOG.json 的 $VERSION 条目，或先 bump VERSION" >&2
  exit 1
fi

say -e "${GREEN}✓ 版本声明一致：$VERSION${NC}"
exit 0
