#!/usr/bin/env bash
# CenkorMES 部署后组合自检
#
# 用途：部署（Docker 或裸装）完成后跑一次，一次性回答「这套到底能不能用」。
# 每次检查独立输出 PASS / FAIL / SKIP，最后汇总；任一 FAIL → 退出码 1。
#
# 用法：
#   bash scripts/post-deploy-check.sh
#   CENKORMES_HEALTH_URL=http://127.0.0.1:8000/api/health bash scripts/post-deploy-check.sh
#
# 可跳过项（容器里没有 systemctl 时会自动 SKIP，无需手工指定）：
#   SKIP_CELERY=1   跳过 celery / beat 活性检查
#   SKIP_ALEMBIC=1  跳过数据库迁移版本检查
#
# 退出码：0 全部通过（含 SKIP）；1 存在 FAIL。
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND="${ROOT}/backend"
ENV_FILE="${BACKEND}/.env"

# 健康检查地址：优先环境变量，其次 .env 里的 APP_PORT，最后回落到 8000
# port 单独留着：后面要用它从监听进程反查解释器
port="8000"
health_url="${CENKORMES_HEALTH_URL:-}"
if [ -z "${health_url}" ]; then
    if [ -f "${ENV_FILE}" ]; then
        parsed="$(grep -E '^[[:space:]]*APP_PORT[[:space:]]*=' "${ENV_FILE}" | tail -n 1 | sed -E 's/^[^=]*=[[:space:]]*//; s/[[:space:]]*#.*$//' | tr -d "\"'")"
        [ -n "${parsed}" ] && port="${parsed}"
    fi
    health_url="http://127.0.0.1:${port}/api/health"
fi

fails=0
skips=0
warns=0

pass() { printf '  \033[32mPASS\033[0m  %s\n' "$*"; }
fail() { printf '  \033[31mFAIL\033[0m  %s\n' "$*"; fails=$((fails + 1)); }
skip() { printf '  \033[33mSKIP\033[0m  %s\n' "$*"; skips=$((skips + 1)); }
warn() { printf '  \033[33mWARN\033[0m  %s\n' "$*"; warns=$((warns + 1)); }

# 找出「服务正在用的解释器」。
# 为什么不能只挑第一个存在的路径：项目里很容易残留一个残缺的 backend/venv
# （本机实测就缺 httpx，import 就炸），挑错了会得出「无法读取迁移版本」这种
# 假结论。所以优先读 /proc/<pid>/exe，其次逐个验证能否真 import alembic。
detect_python() {
    if [ -n "${CENKORMES_PYTHON:-}" ]; then
        printf '%s' "${CENKORMES_PYTHON}"
        return 0
    fi

    local pid="" exe="" cand
    if command -v ss >/dev/null 2>&1; then
        pid="$(ss -lntpH 2>/dev/null | grep ":${port} " | grep -oE 'pid=[0-9]+' | head -n 1 | cut -d= -f2)"
    fi
    if [ -n "${pid}" ] && [ -L "/proc/${pid}/exe" ]; then
        exe="$(readlink -f "/proc/${pid}/exe" 2>/dev/null || true)"
        if [ -n "${exe}" ] && "${exe}" -c 'import alembic' >/dev/null 2>&1; then
            printf '%s' "${exe}"
            return 0
        fi
    fi

    for cand in \
        "/www/server/pyporject_evn/cenkormes/bin/python" \
        "${BACKEND}/venv/bin/python" \
        "$(command -v python3 || true)"; do
        if [ -z "${cand}" ] || [ ! -x "${cand}" ]; then
            continue
        fi
        if "${cand}" -c 'import alembic' >/dev/null 2>&1; then
            printf '%s' "${cand}"
            return 0
        fi
    done

    printf ''
    return 1
}

echo "== CenkorMES 部署自检 =="
echo "   项目根：${ROOT}"
echo "   健康端点：${health_url}"
echo

# ── 1. 健康端点 + 版本一致性 ────────────────────────────────────────────
echo "[1/5] 服务健康与版本"
body="$(curl -fsS --max-time 5 "${health_url}" 2>/dev/null)"

if [ -z "${body}" ]; then
    fail "健康端点不可达（${health_url}）——服务可能没起，或端口与 APP_PORT 不一致"
else
    live_version="$(printf '%s' "${body}" | sed -n 's/.*"version"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p')"
    db_state="$(printf '%s' "${body}" | sed -n 's/.*"db"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p')"

    pass "健康端点可访问，实测版本 ${live_version:-未知}"

    # 版本不一致通常意味着：镜像/产物是旧的，或后端没重启加载新代码
    if [ -f "${ROOT}/VERSION" ]; then
        want_version="$(tr -d '[:space:]' < "${ROOT}/VERSION")"
        if [ "${live_version}" = "${want_version}" ]; then
            pass "运行版本与 VERSION 文件一致（${want_version}）"
        else
            fail "版本不一致：VERSION=${want_version}，运行中=${live_version}——后端可能未重启"
        fi
    fi

    if [ -n "${db_state}" ]; then
        if [ "${db_state}" = "up" ]; then
            pass "数据库连接正常"
        else
            fail "数据库状态异常：${db_state}"
        fi
    fi
fi

# ── 2. 数据库迁移版本 ──────────────────────────────────────────────────
echo "[2/5] 数据库迁移版本"
if [ "${SKIP_ALEMBIC:-0}" = "1" ]; then
    skip "按 SKIP_ALEMBIC=1 跳过"
elif [ ! -d "${BACKEND}/alembic" ]; then
    skip "未发现 alembic 目录"
else
    py="$(detect_python || true)"

    if [ -z "${py}" ]; then
        skip "找不到可用的 python 解释器（可用 CENKORMES_PYTHON 指定）"
    else
        cd "${BACKEND}" || exit 1
        cur="$(PYTHONPATH="${BACKEND}" "${py}" -m alembic current 2>/dev/null | tail -n 1 | awk '{print $1}')"
        head_rev="$(PYTHONPATH="${BACKEND}" "${py}" -m alembic heads 2>/dev/null | tail -n 1 | awk '{print $1}')"
        cd "${ROOT}" || exit 1

        if [ -z "${cur}" ] || [ -z "${head_rev}" ]; then
            skip "无法读取迁移版本（数据库未初始化时可忽略）"
        elif [ "${cur}" = "${head_rev}" ]; then
            pass "迁移版本已到 head（${cur}）"
        else
            fail "迁移未到 head：当前 ${cur}，最新 ${head_rev}——请执行 alembic upgrade head"
        fi
    fi
fi

# ── 3. 存储可写 ────────────────────────────────────────────────────────
echo "[3/5] 存储可写性"
storage_dir="${BACKEND}/data/storage"
if [ ! -d "${storage_dir}" ]; then
    mkdir -p "${storage_dir}" 2>/dev/null
fi
probe_file="${storage_dir}/.write_probe_$$"
if touch "${probe_file}" 2>/dev/null; then
    rm -f "${probe_file}"
    pass "本地上传目录可写（${storage_dir}）"
else
    # 用了云存储时本机不需要可写，这种情况不该判失败
    fail "存储目录不可写（${storage_dir}）——本地驱动会导致上传失败；若已切云存储可忽略"
fi

# ── 4. Celery / Beat ──────────────────────────────────────────────────
echo "[4/5] 异步任务进程"
if [ "${SKIP_CELERY:-0}" = "1" ]; then
    skip "按 SKIP_CELERY=1 跳过"
elif ! command -v systemctl >/dev/null 2>&1; then
    skip "容器环境无 systemctl（Docker 部署由 compose 托管，属正常）"
else
    for unit in cenkormes-celery cenkormes-beat; do
        # 这里必须用 grep -c 而不是 grep -q：-q 匹配成功会立刻退出，上游
        # systemctl 收到 SIGPIPE 返回 141，在 `set -o pipefail` 下整条管道就
        # 成了非零，于是「已安装」会被判成「未安装」。本机实测踩到过。
        unit_count="$(systemctl list-unit-files 2>/dev/null | grep -c "^${unit}\.service" || true)"
        if [ "${unit_count:-0}" -eq 0 ]; then
            skip "${unit} 未安装（纯 Web 使用可忽略）"
        elif systemctl is-active --quiet "${unit}"; then
            pass "${unit} 运行中"
        else
            fail "${unit} 未运行——异步任务与定时任务不会执行"
        fi
    done
fi

# ── 5. 关键配置 ────────────────────────────────────────────────────────
echo "[5/5] 关键配置"
if [ ! -f "${ENV_FILE}" ]; then
    fail "缺少 backend/.env——服务会退回默认配置（含默认密钥，生产会被拒绝启动）"
else
    pass "backend/.env 存在"

    secret_line="$(grep -E '^[[:space:]]*JWT_SECRET[[:space:]]*=' "${ENV_FILE}" | tail -n 1 || true)"
    secret_val="$(printf '%s' "${secret_line}" | sed -E 's/^[^=]*=[[:space:]]*//; s/[[:space:]]*#.*$//' | tr -d "\"'")"
    app_env="$(grep -E '^[[:space:]]*APP_ENV[[:space:]]*=' "${ENV_FILE}" | tail -n 1 | sed -E 's/^[^=]*=[[:space:]]*//; s/[[:space:]]*#.*$//' | tr -d "\"'" || true)"

    case "${secret_val}" in
        ""|change_me*|MUST_CHANGE_ME*|change_me_to_a_long*)
            # dev 下后端不拦（ensure_secure_jwt_secret 只对 prod 生效），
            # 所以这里不能一概判 FAIL，否则本地开发环境一跑就红。
            if [ "${app_env}" = "prod" ]; then
                fail "JWT_SECRET 仍是示例值——APP_ENV=prod 会直接拒绝启动"
            else
                warn "JWT_SECRET 仍是示例值（APP_ENV=${app_env:-未设置}，dev 不拦截，但绝不能用于生产）"
            fi
            ;;
        *)
            if [ "${#secret_val}" -lt 32 ]; then
                if [ "${app_env}" = "prod" ]; then
                    fail "JWT_SECRET 长度 ${#secret_val} < 32——APP_ENV=prod 会拒绝启动"
                else
                    warn "JWT_SECRET 长度 ${#secret_val} < 32（APP_ENV=${app_env:-未设置}，prod 下会被拒绝启动）"
                fi
            else
                pass "JWT_SECRET 已自定义且长度合规"
            fi
            ;;
    esac

    # dev 跑在生产机器上是隐患：异常详情可能回显给前端，行为也与 prod 有差异
    if [ "${app_env}" = "prod" ]; then
        pass "APP_ENV=prod"
    elif [ -n "${app_env}" ]; then
        warn "APP_ENV=${app_env}（非 prod）——若不是本机开发环境，建议改为 prod"
    else
        fail "backend/.env 未设置 APP_ENV（默认按 dev 处理）"
    fi
fi

# ── 汇总 ───────────────────────────────────────────────────────────────
echo
summary="跳过 ${skips} 项"
if [ "${warns}" -gt 0 ]; then
    summary="${summary}，警告 ${warns} 项"
fi

if [ "${fails}" -eq 0 ]; then
    echo "== 自检通过（${summary}）=="
    if [ "${warns}" -gt 0 ]; then
        echo "   警告项不阻塞部署，但上线前应逐条确认。"
    fi
    exit 0
fi
echo "== 自检失败：${fails} 项 FAIL（${summary}）=="
exit 1
