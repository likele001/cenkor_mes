#!/bin/bash
# CenkorMES 本地启动脚本
#   默认 dev：后端 uvicorn --reload（:8000）+ 管理后台 vite（:5174）+ H5 vite（:5173）
#   生产：   ./start.sh --prod   后端编译关闭 reload，前端先 build 再用 vite preview 托管
#
# 依赖：Python 3.10+ / Node 18+ / 本地 MySQL；可选 Redis（Celery 任务）
set -euo pipefail

cd "$(dirname "$0")"

BACKEND_PORT="${BACKEND_PORT:-8000}"
ADMIN_PORT="${ADMIN_PORT:-5174}"
H5_PORT="${H5_PORT:-5173}"
MODE="dev"
if [ "${1:-}" = "--prod" ]; then MODE="prod"; fi

# 前端 dev 的 /api 代理跟随后端端口，避免端口被占用/被改而串到其它服务（如其它项目占8000）
export VITE_API_PROXY="${VITE_API_PROXY:-http://127.0.0.1:${BACKEND_PORT}}"

echo "=== CenkorMES 启动（${MODE} 模式）==="

# 1) 后端 Python 环境
if [ ! -d backend/venv ]; then
    echo ">>> 创建后端虚拟环境并安装依赖..."
    python3 -m venv backend/venv
    backend/venv/bin/pip install --upgrade pip
    backend/venv/bin/pip install -r backend/requirements.txt
fi

# 2) 环境配置检查
if [ ! -f backend/.env ]; then
    echo "[提示] 未找到 backend/.env，首次可: cp backend/env.example backend/.env，再编辑数据库连接。"
fi

# 3) 启动后端
if [ "$MODE" = "prod" ]; then
    echo ">>> 启动后端 (${BACKEND_PORT}, 无 --reload)"
    ( cd backend && exec venv/bin/uvicorn app.main:app --host 0.0.0.0 --port "$BACKEND_PORT" ) &
else
    echo ">>> 启动后端 (${BACKEND_PORT}, --reload)"
    ( cd backend && exec venv/bin/uvicorn app.main:app --host 0.0.0.0 --port "$BACKEND_PORT" --reload ) &
fi
BACKEND_PID=$!

# 4) 前端
start_frontend() {
    local name="$1" dir="$2" port="$3"
    echo ">>> 准备前端 ${name} ..."
    ( cd "$dir" && npm install --silent ) &
    wait $!
    if [ "$MODE" = "prod" ]; then
        echo ">>> 构建 ${name} 并以 preview 托管 (:${port})"
        ( cd "$dir" && npm run build && npm run preview -- --host 0.0.0.0 --port "$port" ) &
    else
        ( cd "$dir" && npm run dev -- --port "$port" ) &
    fi
}

start_frontend "管理后台" frontend-admin-pro "$ADMIN_PORT"
ADMIN_PID=$!
start_frontend "H5 移动端" frontend-h5 "$H5_PORT"
H5_PID=$!

echo ""
echo "=== 服务已启动 ==="
echo "  管理后台: http://localhost:${ADMIN_PORT}"
echo "  H5 移动端: http://localhost:${H5_PORT}"
echo "  API:        http://localhost:${BACKEND_PORT}/api   (文档: /docs)"
echo "  默认管理员: admin / admin123"
echo ""
echo "按 Ctrl+C 停止全部服务"

trap 'kill $BACKEND_PID $ADMIN_PID $H5_PID 2>/dev/null || true' EXIT
wait
